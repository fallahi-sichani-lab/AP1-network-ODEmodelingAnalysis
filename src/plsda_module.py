import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import scipy.stats as stats
import seaborn as sns
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import accuracy_score
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.model_selection import cross_val_predict, StratifiedKFold, KFold, LeaveOneOut
from sklearn.metrics import roc_curve, auc
from sklearn.linear_model import LogisticRegression
from sklearn.utils import resample
from scipy.interpolate import interp1d

class PLSDA:
    def __init__(self, n_components=2, cv_folds=5, one_hot_encode=False, downsample_ratio=3, cv_method = 'kfold'):
        self.n_components = n_components
        self.cv_folds = cv_folds
        self.one_hot_encode = one_hot_encode
        self.pls_da = PLSRegression(n_components=self.n_components)
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.one_hot_encoder = OneHotEncoder(sparse_output=False)
        self.downsample_ratio = downsample_ratio
        self.cv_method = cv_method 

    def balance_classes(self, X, y, random_state = None):
        """
        Balance classes by downsampling the majority class if it exceeds 80% of the data.
        
        Parameters:
        - X: Features
        - y: Labels
        
        Returns:
        - X_balanced, y_balanced: Balanced datasets
        """
        if self.downsample_ratio is None:
            return X, y
        rs = 42 if random_state is None else random_state
        unique, counts = np.unique(y, return_counts=True)
        total_samples = len(y)
        
        if len(unique) == 2:  # Binary classification
            majority_class = unique[np.argmax(counts)]
            minority_class = unique[np.argmin(counts)]
            
            majority_ratio = max(counts) / total_samples
            minority_ratio = min(counts) / total_samples
            
            if majority_ratio > 0.8 and minority_ratio < 0.2:
                # Downsample majority class
                X_majority = X[y == majority_class]
                y_majority = y[y == majority_class]
                X_minority = X[y == minority_class]
                y_minority = y[y == minority_class]
                
                n_minority = len(y_minority)
                n_downsample = n_minority * self.downsample_ratio
                
                X_majority_downsampled, y_majority_downsampled = resample(
                    X_majority, y_majority,
                    n_samples=n_downsample,
                    random_state=rs
                )
                
                X_balanced = np.vstack((X_majority_downsampled, X_minority))
                y_balanced = np.hstack((y_majority_downsampled, y_minority))
                
                return X_balanced, y_balanced
        
        return X, y

    def preprocess(self, X, y=None, downsample = False, fit_scaler = True, random_state = 42):
        if y is not None and downsample:
            X, y = self.balance_classes(X, y, random_state=random_state)
        X_log_transformed = np.log1p(X)
        if fit_scaler:
            X_scaled = self.scaler.fit_transform(X_log_transformed)
        else:
            X_scaled = self.scaler.transform(X_log_transformed)

        return (X_scaled, y) if y is not None else X_scaled

    def preprocess_transform(self, X):
        X_log_transformed = np.log1p(X)
        X_scaled = self.scaler.transform(X_log_transformed)
        return X_scaled  

    def encode_labels(self, y):
        if self.one_hot_encode:
            y_encoded = self.one_hot_encoder.fit_transform(y.reshape(-1, 1))
        else:
            y_encoded = self.label_encoder.fit_transform(y)
        return y_encoded
    
    def find_optimal_components(self, X, y, max_components=15, show_plot=True, save_plot=False, 
                        improvement_threshold=0.01, show_thresholds_on_plot=False):
        """
        Finds the optimal number of components for Partial Least Squares Discriminant Analysis (PLS-DA)
        with consideration for diminishing returns.

        Parameters:
            X (pandas.DataFrame): The input features.
            y (pandas.Series): The target variable.
            max_components (int): The maximum number of components to consider. Defaults to 15.
            show_plot (bool): Whether to display the plot.
            save_plot (bool): Whether to save the plot.
            improvement_threshold (float): Minimum improvement in AUC required to justify 
                                        additional components (default: 0.01 or 1%).
            show_thresholds_on_plot (bool): Whether to show threshold indicators on the plot.

        Returns:
            tuple: A tuple containing the optimal number of components and the mean cross-validation AUC scores.
        """
        # Convert to numpy arrays if they're pandas objects
        is_pandas = isinstance(X, pd.DataFrame)
        X_array = X.values if is_pandas else X
        y_array = y.values.ravel() if isinstance(y, (pd.DataFrame, pd.Series)) else y
        
        cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
        mean_aucs = []
        std_aucs = []

        # Determine the absolute maximum number of components possible
        # n_components cannot be > n_samples in the smallest training fold
        n_samples = len(y_array)
        smallest_train_size = n_samples - (n_samples // self.cv_folds)
        effective_max_components = min(max_components, smallest_train_size)

        for n_components in range(1, max_components + 1):
            pls = PLSRegression(n_components=n_components)
            aucs = []

            for train_idx, test_idx in cv.split(X_array, y_array):
                # Use correct indexing based on input type
                if is_pandas:
                    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
                else:
                    X_train, X_test = X_array[train_idx], X_array[test_idx]
                    y_train, y_test = y_array[train_idx], y_array[test_idx]

                # Dynamically adjust n_components if it exceeds the number of samples in the training fold
                if n_components > len(y_train):
                    print(f"Warning: n_components ({n_components}) > n_samples in fold ({len(y_train)}). Skipping this component count for this fold.")
                    continue

                # Process training data (with downsampling if enabled)
                if self.downsample_ratio is not None:
                    X_train_downsampled, y_train_downsampled = self.balance_classes(X_train, y_train)
                else:
                    X_train_downsampled, y_train_downsampled = X_train, y_train
                
                # Apply log transform and scaling to training data
                X_train_log = np.log1p(X_train_downsampled)
                self.scaler.fit(X_train_log)
                X_train_scaled = self.scaler.transform(X_train_log)
                
                # Process test data (without downsampling)
                X_test_log = np.log1p(X_test)
                X_test_scaled = self.scaler.transform(X_test_log)
                
                # Encode labels for training
                if self.one_hot_encode:
                    y_train_encoded = self.one_hot_encoder.fit_transform(
                        y_train_downsampled.reshape(-1, 1) if not isinstance(y_train_downsampled, pd.Series) 
                        else y_train_downsampled.values.reshape(-1, 1)
                    )
                else:
                    y_train_encoded = self.label_encoder.fit_transform(y_train_downsampled)

                # Fit PLS model on processed training data
                pls.fit(X_train_scaled, y_train_encoded)
                
                # Predict on test data 
                y_score = pls.predict(X_test_scaled).ravel()

                # Calculate AUC using the original test labels
                fpr, tpr, _ = roc_curve(y_test, y_score)
                aucs.append(auc(fpr, tpr))

            mean_aucs.append(np.mean(aucs))
            std_aucs.append(np.std(aucs))

        # The rest of the method (finding optimal components, plotting, etc.) remains the same
        # Method 1: Maximum AUC
        max_auc_components = np.argmax(mean_aucs) + 1
        
        # Method 2: Diminishing returns
        diminishing_returns_components = 1
        for i in range(1, len(mean_aucs)):
            if mean_aucs[i] - mean_aucs[i-1] >= improvement_threshold:
                diminishing_returns_components = i + 1
            else:
                # Check if any subsequent component gives significant improvement
                if not any(mean_aucs[j] - mean_aucs[j-1] >= improvement_threshold 
                        for j in range(i+1, len(mean_aucs)) if j < len(mean_aucs)):
                    break
        
        # Plotting the results
        fig, ax = plt.figure(figsize=(8, 6)), plt.subplot(111)
        ax.plot([0, 1], [0, mean_aucs[0]], '-', color='navy')
        ax.errorbar(range(1, max_components + 1), mean_aucs, yerr=std_aucs, 
                    fmt='-o', color='navy', capsize=5)
        ax.set_ylim(0, 1)
        ax.set_xlabel('Number of Components')
        ax.set_ylabel('Average AUC (± std)\n ('f'{self.cv_folds}-Fold CV)')
        ax.set_xlim(0, max_components + 0.5)
        
        # Only show threshold indicators if requested
        if show_thresholds_on_plot:
            ax.axvline(x=max_auc_components, linestyle='--', color='green', alpha=0.5, 
                    label=f'Max AUC: {max_auc_components}')
            ax.axvline(x=diminishing_returns_components, linestyle='--', color='red', alpha=0.5, 
                    label=f'Diminishing returns: {diminishing_returns_components}')
            ax.legend(loc='lower right')
        
        ax.fill_between(range(1, max_components + 1), 
                        np.array(mean_aucs) - np.array(std_aucs), 
                        np.array(mean_aucs) + np.array(std_aucs), 
                        alpha=0.2)
        
        # Create inset axes with dynamic range
        axins = fig.add_axes([0.55, 0.25, 0.3, 0.3])
        axins.plot([0, 1], [0, mean_aucs[0]], '-', color='navy')
        axins.plot(range(1, max_components + 1), mean_aucs, '-o', color='navy')
        
        # Dynamically set y-range for inset based on data
        min_auc = min(mean_aucs)
        max_auc = max(mean_aucs)
        range_auc = max_auc - min_auc
        
        # Set inset y limits with padding to show variation better
        y_min = max(0, min_auc - range_auc * 0.1)
        y_max = min(1, max_auc + range_auc * 0.1)
        
        # If range is very small, create a meaningful zoom window
        if range_auc < 0.05:
            mid_point = (y_min + y_max) / 2
            y_min = max(0, mid_point - 0.05)
            y_max = min(1, mid_point + 0.05)
        
        axins.set_ylim(y_min, y_max)
        
        # Only show threshold indicators in inset if requested
        if show_thresholds_on_plot:
            axins.axvline(x=max_auc_components, linestyle='--', color='green', alpha=0.5)
            axins.axvline(x=diminishing_returns_components, linestyle='--', color='red', alpha=0.5)
        
        if save_plot:
            plt.savefig('optimal_components_plot.pdf', dpi=300, bbox_inches='tight')

        if show_plot:
            plt.show()
        else:
            plt.close(fig)
        
        print(f'Maximum AUC at components: {max_auc_components}')
        print(f'Diminishing returns at components: {diminishing_returns_components}')
        print(f'Maximum mean AUC: {max(mean_aucs):.3f} ± {std_aucs[max_auc_components-1]:.3f}')
        print(f'AUC at diminishing returns: {mean_aucs[diminishing_returns_components-1]:.3f} ± {std_aucs[diminishing_returns_components-1]:.3f}')
        
        recommended_components = diminishing_returns_components
        print(f'Recommended number of components: {recommended_components}')
        
        return recommended_components, mean_aucs

    def fit_transform(self, X, y):
        if self.n_components is None:
            self.n_components = self.determine_optimal_components(X, y)
        self.pls_da = PLSRegression(n_components=self.n_components)
        
        # Preprocess data
        if self.downsample_ratio is not None:   
            X_downsampled, y_balanced = self.balance_classes(X, y)
        else:
            X_downsampled = X
            y_balanced = y
        X_scaled, y_balanced = self.preprocess(X_downsampled, y_balanced)
        y_encoded = self.encode_labels(y_balanced)
        
        # Fit PLS model
        self.pls_da.fit(X_scaled, y_encoded)
        X_pls = self.pls_da.transform(X_scaled)
        
        # Get model components
        x_scores = self.pls_da.x_scores_
        x_loadings = self.pls_da.x_loadings_
        
        # Calculate X variance explained (similar to MATLAB approach)
        # Using orthogonal scores to calculate variance directly
        x_var_total = np.sum(X_scaled**2)
        self.x_variance_explained = []
        for i in range(self.n_components):
            component_var = np.sum(x_scores[:, i]**2)
            var_explained = component_var / x_var_total * 100
            self.x_variance_explained.append(var_explained)
        
        # Calculate Y variance explained using the MATLAB PLS approach
        # For PLSDA, the Y variance is calculated based on how well each component
        # separates the classes, similar to how MATLAB calculates it
        
        # Get the reduced rank regression coefficient matrix
        B_pls = self.pls_da.coef_
        y_mean = np.mean(y_encoded)
        y_centered = y_encoded - y_mean
        
        # Calculate total Y variance
        TSS = np.sum(y_centered**2)  # Total Sum of Squares
        
        # Calculate explained Y variance for each component
        self.y_variance_explained = []
        cumulative_y_var = 0
        
        # Calculate Y variance incrementally for each component
        for i in range(self.n_components):
            # Create a model with i+1 components
            temp_pls = PLSRegression(n_components=i+1)
            temp_pls.fit(X_scaled, y_encoded)
            
            # Get predictions
            y_pred = temp_pls.predict(X_scaled)
            if len(y_pred.shape) > 1:
                y_pred = y_pred.ravel()
            
            # Calculate variance explained using MATLAB-like approach
            y_pred_centered = y_pred - y_mean
            ESS = np.sum(y_pred_centered**2)  # Explained Sum of Squares
            
            # Similar to MATLAB's approach for calculating Y variance
            var_explained_cumulative = ESS / TSS * 100
            
            # Calculate incremental variance
            if i == 0:
                var_explained = var_explained_cumulative
            else:
                prev_cumulative = sum(self.y_variance_explained)
                var_explained = max(0, var_explained_cumulative - prev_cumulative)
            
            print(f"Component {i+1}:")
            print(f"Cumulative Y variance: {var_explained_cumulative:.2f}%")
            print(f"Incremental Y variance: {var_explained:.2f}%")
            
            self.y_variance_explained.append(var_explained)
        
        # Convert to numpy arrays
        self.x_variance_explained = np.array(self.x_variance_explained)
        self.y_variance_explained = np.array(self.y_variance_explained)
        
        return X_pls, self.x_variance_explained, self.y_variance_explained, y_encoded, X_downsampled, y_balanced
        # return X_pls, variance_explained_percent, y_encoded, X_downsampled, y_balanced

    def plot_scores(self, X_pls, x_variance_explained, y_variance_explained, y, lv1=0, lv2=1, 
                class_descriptions=None, colors=None, alpha_values=None, line_colors=None, size = None,
                show_plot=True, save_plot=False):
        """
        Plot the scores for any two specified latent variables (LVs).
        
        Parameters:
        - X_pls: Scores from the PLS-DA model.
        - x_variance_explained: Variance explained by each LV.
        - y_variance_explained: Variance explained by each LV.
        - y: Class labels.
        - lv1: Index of the first latent variable to plot (default is 0 for LV1).
        - lv2: Index of the second latent variable to plot (default is 1 for LV2).
                - class_descriptions: Dictionary mapping class labels to descriptions.
            - colors: List of colors for each class. If None, default colors will be used.
            - alpha_values: List of alpha values for each class. If None, default values will be used.
            - line_colors: List of line colors for each class. If None, default colors will be used.
            - size: List of sizes for each class. If None, default size will be used.
        """
        # Default class descriptions if not provided
        if class_descriptions is None:
            class_descriptions = {0: "Other", 1: "Class of Interest"}
    
        # Default colors and alpha values
        if colors is None:
            colors = ['darkslategray', 'darkorange']
        if alpha_values is None:
            alpha_values = [0.4, 0.7]
        if line_colors is None:
            line_colors = ['k', 'k']
        if size is None:
            size = [100, 100]
        
        plt.figure(figsize=(8, 8))

        for i, (color, alpha, line_color) in enumerate(zip(colors, alpha_values, line_colors)):
            mask = y == i
            if mask.any():  # Only plot if there are samples for this class
                plt.scatter(X_pls[mask, lv1], X_pls[mask, lv2], 
                            color=color, label=class_descriptions.get(i, f"Class {i}"),
                            edgecolors=line_color, s=size[i], alpha=alpha, marker='o')

        plt.xlabel(f'LV {lv1 + 1} (X: {x_variance_explained[lv1]:.2f}%, Y: {y_variance_explained[lv1]:.2f}%)')
        plt.ylabel(f'LV {lv2 + 1} (X: {x_variance_explained[lv2]:.2f}%, Y: {y_variance_explained[lv2]:.2f}%)')
        plt.legend()
        if save_plot:
            plt.savefig('scores_plot.pdf', dpi=500, bbox_inches='tight')
        if show_plot:
            plt.show()

    def plot_scores_with_density(self, X_pls, x_variance_explained, y_variance_explained, y, lv1=0, lv2=1, 
                     class_descriptions=None, colors=None, alpha_values=None, line_colors=None, size=None,
                     show_plot=True, save_plot=False):
        """
        Plot the scores for any two specified latent variables (LVs) with density distributions and p-values.
        
        Parameters:
        - X_pls: Scores from the PLS-DA model.
        - x_variance_explained: X-variance explained by each LV.
        - y_variance_explained: Y-variance explained by each LV.
        - y: Class labels.
        - lv1: Index of the first latent variable to plot (default is 0 for LV1).
        - lv2: Index of the second latent variable to plot (default is 1 for LV2).
        - class_descriptions: Dictionary mapping class labels to descriptions.
        - colors: List of colors for each class. If None, default colors will be used.
        - alpha_values: List of alpha values for each class. If None, default values will be used.
        - line_colors: List of line colors for each class. If None, default colors will be used.
        - size: List of sizes for each class. If None, default size will be used.
        """
        import matplotlib.gridspec as gridspec

        
        # Default class descriptions if not provided
        if class_descriptions is None:
            class_descriptions = {0: "Other", 1: "Class of Interest"}

        # Default colors and alpha values
        if colors is None:
            colors = ['darkslategray', 'darkorange']
        if alpha_values is None:
            alpha_values = [0.4, 0.7]
        if line_colors is None:
            line_colors = ['k', 'k']
        if size is None:
            size = [100, 100]
        
        # Create a figure with gridspec
        fig = plt.figure(figsize=(8, 8))
        gs = gridspec.GridSpec(4, 4)
        
        # Create main scatter plot (larger, takes most of the space)
        ax_main = plt.subplot(gs[1:, 0:3])
        ax_x_density = plt.subplot(gs[0, 0:3], sharex=ax_main)
        ax_y_density = plt.subplot(gs[1:, 3], sharey=ax_main)
        
        # Turn off tick labels for density plots
        ax_x_density.tick_params(axis='x', labelbottom=False)
        ax_y_density.tick_params(axis='y', labelleft=False)
        
        # Prepare for p-value calculations
        unique_classes = np.unique(y)
        if len(unique_classes) == 2:
            # Get indices for both classes
            class0_idx = y == unique_classes[0]
            class1_idx = y == unique_classes[1]
            
            # Calculate KS test p-values for both LVs
            u_stat_lv1, p_value_lv1 = stats.ttest_ind(X_pls[class0_idx, lv1], X_pls[class1_idx, lv1])
            u_stat_lv2, p_value_lv2 = stats.ttest_ind(X_pls[class0_idx, lv2], X_pls[class1_idx, lv2])

            # Format p-values in scientific notation
            lv1_pval_text = f'p = {p_value_lv1:.1e}'
            lv2_pval_text = f'p = {p_value_lv2:.1e}'
                        
            # Determine significance indicators
            # def get_significance_symbol(p_value):
            #     if p_value < 0.001:
            #         return '***'
            #     elif p_value < 0.01:
            #         return '**'
            #     elif p_value < 0.05:
            #         return '*'
            #     else:
            #         return 'ns'
            
            # lv1_sig = get_significance_symbol(p_value_lv1)
            # lv2_sig = get_significance_symbol(p_value_lv2)
        
        # Plot scatter for each class in main plot
        for i, (color, alpha, line_color) in enumerate(zip(colors, alpha_values, line_colors)):
            if i >= len(unique_classes):
                continue
                
            mask = y == unique_classes[i]
            if mask.any():  # Only plot if there are samples for this class
                # Main scatter plot
                ax_main.scatter(X_pls[mask, lv1], X_pls[mask, lv2], 
                            color=color, label=class_descriptions.get(unique_classes[i], f"Class {unique_classes[i]}"),
                            edgecolors=line_color, s=size[i], alpha=alpha, marker='o')
                
                # X-axis density plot
                sns.kdeplot(x=X_pls[mask, lv1], ax=ax_x_density, color=color, fill=True, alpha=0.5, linewidth=2)
                
                # Y-axis density plot
                sns.kdeplot(y=X_pls[mask, lv2], ax=ax_y_density, color=color, fill=True, alpha=0.5, linewidth=2)

        from matplotlib.ticker import LinearLocator, NullLocator, FormatStrFormatter

        # --- Keep density plots aligned to scatter limits (optional, for consistency) ---
        ax_x_density.set_xlim(ax_main.get_xlim())
        ax_y_density.set_ylim(ax_main.get_ylim())

        # --- Top density: 3 ticks on Y (density scale) ---
        ax_x_density.yaxis.set_major_locator(LinearLocator(3))
        ax_x_density.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

        # --- Right density: 3 ticks on X (density scale) ---
        ax_y_density.xaxis.set_major_locator(LinearLocator(3))
        ax_y_density.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))

        # --- Hide the unused axes on density plots for a cleaner look ---
        # ax_x_density.xaxis.set_major_locator(NullLocator())  # no x ticks on top density
        # ax_y_density.yaxis.set_major_locator(NullLocator())  # no y ticks on right density

        # --- Ensure tick labels are visible ---
        ax_x_density.tick_params(axis='y', labelleft=True)
        ax_y_density.tick_params(axis='x', labelbottom=True)


        # Set labels for main plot
        ax_main.set_xlabel(f'LV {lv1 + 1} (X: {x_variance_explained[lv1]:.2f}%, Y: {y_variance_explained[lv1]:.2f}%)')
        ax_main.set_ylabel(f'LV {lv2 + 1} (X: {x_variance_explained[lv2]:.2f}%, Y: {y_variance_explained[lv2]:.2f}%)')
        
        # Add legend to main plot
        ax_main.legend(loc='best')
        
        # Add p-value annotations if we have two classes
        if len(unique_classes) == 2:
            # Add p-value to x-axis density plot
            ax_x_density.annotate(f'{lv1_pval_text}', 
                                xy=(0.5, 0.9), xycoords='axes fraction',
                                ha='right', va='center', fontsize=14,
                                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
            # Add p-value to y-axis density plot
            ax_y_density.annotate(f'{lv2_pval_text}', 
                                xy=(0.5, 0.9), xycoords='axes fraction',
                                ha='right', va='center', fontsize=14,
                                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
        
        # Adjust the layout
        plt.tight_layout()
        
        if save_plot:
            plt.savefig('scores_plot_with_density.pdf', dpi=500, bbox_inches='tight')
        if show_plot:
            plt.show()
        
        return fig

    
    # def cross_validation(self, X, y):
    #     scores_list = []
    #     true_labels = []


    #     if self.cv_method == 'loo':
    #         cv = LeaveOneOut()  
    #     else:
    #         cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)

    #     for train_index, test_index in cv.split(X, y):
    #         X_train, X_test = X[train_index], X[test_index]
    #         y_train, y_test = y[train_index], y[test_index]

    #         # Process training data (downsample + fit scaler)
    #         X_train_proc, y_train_bal = self.preprocess(X_train, y_train, 
    #                                                 downsample=True, 
    #                                                 fit_scaler=True)

    #         y_train_encoded = self.encode_labels(y_train_bal)
    #         self.pls_da.fit(X_train_proc, y_train_encoded)
    #         X_test_proc = self.preprocess(X_test, fit_scaler=False)
    #         fold_scores = self.pls_da.predict(X_test_proc)
    #         scores_list.extend(fold_scores.ravel())
    #         true_labels.extend(y_test)

    #         # # Fit PLS model
    #         # self.pls_da.fit(X_train, y_train)
    #         # y_pred = self.pls_da.predict(X_test)

    #         # # Store predictions and true labels
    #         # scores_list.append(y_pred)
    #         # true_labels.append(y_test)
        
    #     #y_scores = cross_val_predict(self.pls_da, X_scaled, y_encoded, cv=cv, method='predict')
    #     return np.array(scores_list), np.array(true_labels)
    def cross_validation(self, X, y):
    # Convert to numpy arrays if they're pandas objects
        X_array = X.values if isinstance(X, pd.DataFrame) else X
        y_array = y.values.ravel() if isinstance(y, (pd.DataFrame, pd.Series)) else y
        
        # Setup cross-validation
        if self.cv_method == 'loo':
            cv = LeaveOneOut()  
        else:
            cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
        
        predictions = []
        true_labels = []
        
        # Run cross-validation using numpy arrays
        for train_idx, test_idx in cv.split(X_array, y_array):
            # Use numpy arrays with direct indexing
            X_train, X_test = X_array[train_idx], X_array[test_idx]
            y_train, y_test = y_array[train_idx], y_array[test_idx]
            
            # Process training data (with or without downsampling)
            if self.downsample_ratio is not None:
                X_train_downsampled, y_train_downsampled = self.balance_classes(X_train, y_train)
            else:
                X_train_downsampled, y_train_downsampled = X_train, y_train
            
            # Apply log transform and scaling
            X_train_log = np.log1p(X_train_downsampled)
            self.scaler.fit(X_train_log)
            X_train_scaled = self.scaler.transform(X_train_log)
            
            # Encode labels
            if self.one_hot_encode:
                y_train_encoded = self.one_hot_encoder.fit_transform(y_train_downsampled.reshape(-1, 1))
            else:
                y_train_encoded = self.label_encoder.fit_transform(y_train_downsampled)
            
            # Process test data (no downsampling)
            X_test_log = np.log1p(X_test)
            X_test_scaled = self.scaler.transform(X_test_log)
            
            # Fit and predict
            self.pls_da.fit(X_train_scaled, y_train_encoded)
            fold_preds = self.pls_da.predict(X_test_scaled).ravel()
            
            # Store results
            predictions.extend(fold_preds)
            true_labels.extend(y_test)
        
        return np.array(predictions), np.array(true_labels)

    # def plot_roc(self, y_scores, y, show_plot=True, save_plot=False):
    #     # For binary classification, ensure you're handling the scores correctly
    #     # if y_scores.shape[1] == 1:
    #     #     fpr, tpr, thresholds = roc_curve(y, y_scores.ravel())
    #     #     roc_auc = auc(fpr, tpr)
    #     # else:
    #     #     fpr, tpr, thresholds = roc_curve(y, y_scores[:, 1])
    #     #     roc_auc = auc(fpr, tpr)
    #     fpr, tpr, thresholds = roc_curve(y, y_scores)
    #     roc_auc = auc(fpr, tpr)
    #     # Plot ROC curve
    #     plt.figure()
    #     plt.plot(fpr, tpr, color='darkorange', lw=2, label='ROC curve (area = %0.2f)' % roc_auc)
    #     plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    #     plt.xlim([0.0, 1.0])
    #     plt.ylim([0.0, 1.05])
    #     plt.xlabel('FPR')
    #     plt.ylabel('TPR')
    #     plt.title('10-Fold Cross-Validated ROC Curve')
    #     plt.legend(loc="lower right")

    #     if save_plot:
    #         plt.savefig('roc_plot.pdf', dpi=500, bbox_inches='tight')
    #     if show_plot:
    #         plt.show()


    def compute_vip(self):
        """
        Compute the Variable Importance in Projection (VIP) scores for the PLS-DA model.

        Returns:
            vips (numpy.ndarray): Array of VIP scores for each variable.
        """
        t = self.pls_da.x_scores_
        w = self.pls_da.x_weights_
        q = self.pls_da.y_loadings_
        p, h = w.shape
        vips = np.zeros((p,))
        s = np.diag(t.T @ t @ q.T @ q).reshape(h, -1)
        total_s = np.sum(s)
        for i in range(p):
            weight = np.array([(w[i, j] / np.linalg.norm(w[:, j]))**2 for j in range(h)])
            vips[i] = np.sqrt(p * (s.T @ weight) / total_s)
        return vips

    def compute_signed_vip(self, X, y, feature_names):
        vip_scores = self.compute_vip()
        lr = LogisticRegression(max_iter=2000).fit(X, y)
        coef_signs = np.sign(lr.coef_[0])
        signed_vip_scores = vip_scores * coef_signs
        return signed_vip_scores, feature_names

    def plot_signed_vip(self, signed_vip_scores, feature_names, colors=['darkslategray', 'darkorange'], custom_order=None, show_plot=True, save_plot=False):
        """
        Plot signed VIP scores as horizontal bars.
        
        Parameters:
        - signed_vip_scores: Array of VIP scores with signs
        - feature_names: List of feature names
        - colors: List of two colors for negative and positive scores
        - custom_order: Optional list of feature names in desired order. If None, will use score-based ordering
        """
        if custom_order is not None:
            # Verify all features are in custom_order
            if not all(feat in custom_order for feat in feature_names):
                raise ValueError("custom_order must contain all feature names")
            
            # Create mapping of features to their VIP scores
            score_dict = dict(zip(feature_names, signed_vip_scores))
            
            # Use custom order
            sorted_feature_names = custom_order
            sorted_vip_scores = [score_dict[feat] for feat in custom_order]
        else:
            # Use original score-based ordering
            positive_indices = [i for i, score in enumerate(signed_vip_scores) if score >= 0]
            negative_indices = [i for i, score in enumerate(signed_vip_scores) if score < 0]

            positive_sorted = sorted([(signed_vip_scores[i], feature_names[i]) for i in positive_indices], 
                                    key=lambda x: x[0], reverse=True)
            negative_sorted = sorted([(signed_vip_scores[i], feature_names[i]) for i in negative_indices], 
                                    key=lambda x: x[0])

            sorted_vip_scores = [score for score, _ in negative_sorted + positive_sorted]
            sorted_feature_names = [name for _, name in negative_sorted + positive_sorted]

        plt.figure(figsize=(8, 8))
        colors = [colors[0] if score < 0 else colors[1] for score in sorted_vip_scores]
        
        # Create horizontal bar plot
        bars = plt.barh(range(len(sorted_feature_names)), sorted_vip_scores, color=colors, edgecolor='black', linewidth=1.8)

        # Set y-ticks and labels
        plt.yticks(range(len(sorted_feature_names)), sorted_feature_names)
        
        # Invert y-axis to have the highest positive value at the top
        plt.gca().invert_yaxis()
        
        # Center the plot on 0
        max_abs_vip = max(abs(max(sorted_vip_scores)), abs(min(sorted_vip_scores)))
        plt.xlim(-max_abs_vip, max_abs_vip)
        
        # Add vertical lines at -1, 0, and 1
        plt.axvline(x=-1, color='r', linestyle='--', linewidth=1.8)
        plt.axvline(x=0, color='k', linestyle='--', linewidth=1.2)
        plt.axvline(x=1, color='r', linestyle='--', linewidth=1.8)
        
        plt.xlabel('VIP Score')
        plt.ylabel('Features')
        plt.tight_layout()
        if save_plot:
            plt.savefig('signed_vip_scores.pdf', dpi=500, bbox_inches='tight')
        plt.show()
       

    def loading_scores(self):
        # Calculate loading scores
        loading_scores = self.pls_da.x_loadings_
        return loading_scores

    def plot_loading_scores(self, feature_names):
        loadings = self.pls_da.x_loadings_

        fig, axs = plt.subplots(1, 2, figsize=(14, 8), sharey=True)

        # Component 1 Loadings
        axs[0].barh(range(len(feature_names)), loadings[:, 0], align='center')
        axs[0].set_yticks(range(len(feature_names)))
        axs[0].set_yticklabels(feature_names)
        axs[0].invert_yaxis()  # Invert y axis to have the first feature on top
        axs[0].set_title('PLS Component 1 Loadings')

        # Component 2 Loadings
        axs[1].barh(range(len(feature_names)), loadings[:, 1], align='center')
        axs[1].set_title('PLS Component 2 Loadings')

        plt.show()


    
    def plot_mean_roc(self, X, y, show_plot=True, save_plot=False):
        # Convert X and y to numpy arrays if they're pandas objects
        if isinstance(X, pd.DataFrame) or isinstance(X, pd.Series):
            X = X.values
        if isinstance(y, pd.DataFrame) or isinstance(y, pd.Series):
            y = y.values.ravel()
            
        # Setup cross-validation
        if self.cv_method == 'loo':
            cv = LeaveOneOut()
        else:
            cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
            
        tprs = []
        aucs = []
        mean_fpr = np.linspace(0, 1, 100)

        fig, ax = plt.subplots(figsize=(8, 8))
        
        for i, (train, test) in enumerate(cv.split(X, y)):
            # Get fold data
            X_train, X_test = X[train], X[test]
            y_train, y_test = y[train], y[test]
            
            # Process training data (with downsampling)
            if self.downsample_ratio is not None:
                X_train_downsampled, y_train_downsampled = self.balance_classes(X_train, y_train)
            else:
                X_train_downsampled, y_train_downsampled = X_train, y_train
            
            # Apply log transform and scaling to training data
            X_train_log = np.log1p(X_train_downsampled)
            self.scaler.fit(X_train_log)  # Fit scaler on training data
            X_train_scaled = self.scaler.transform(X_train_log)
            
            # Encode training labels
            if self.one_hot_encode:
                y_train_encoded = self.one_hot_encoder.fit_transform(y_train_downsampled.reshape(-1, 1))
            else:
                y_train_encoded = self.label_encoder.fit_transform(y_train_downsampled)
            
            # Process test data (WITHOUT downsampling)
            X_test_log = np.log1p(X_test)
            X_test_scaled = self.scaler.transform(X_test_log)  # Transform only
            
            # Skip if test set has only one class
            if len(np.unique(y_test)) < 2:
                continue
            
            # Fit model on processed training data
            self.pls_da.fit(X_train_scaled, y_train_encoded)
            
            # Predict on test data 
            y_score = self.pls_da.predict(X_test_scaled)
            y_score = np.ravel(y_score)

            # Calculate ROC curve for this fold
            fpr, tpr, _ = roc_curve(y_test, y_score)
            
            # Remove duplicate FPR values
            unique_fpr, unique_indices = np.unique(fpr, return_index=True)
            unique_tpr = tpr[unique_indices]
            
            # Use interpolation to standardize the ROC curve
            if len(unique_fpr) > 1:
                interp_tpr = interp1d(unique_fpr, unique_tpr, kind='slinear', 
                                    bounds_error=False, fill_value=(0, 1))(mean_fpr)
            else:
                interp_tpr = np.where(mean_fpr <= unique_fpr[0], 0, 1)
            
            interp_tpr[0] = 0.0  # Ensure starts at 0
            roc_auc = auc(fpr, tpr)
            tprs.append(interp_tpr)
            aucs.append(roc_auc)

        # Handle case where no valid folds were found
        if not tprs:
            print("Unable to calculate ROC curve. All splits resulted in single-class test sets.")
            return None

        # Calculate mean ROC curve
        mean_tpr = np.mean(tprs, axis=0)
        mean_tpr[-1] = 1.0  # Ensure ends at 1
        mean_auc = auc(mean_fpr, mean_tpr)
        std_auc = np.std(aucs)
        avg_auc = np.mean(aucs)

        # Plot mean ROC curve
        ax.plot(mean_fpr, mean_tpr, color='darkorange',
                label=f'ROC AUC = {mean_auc:.2f} ± {std_auc:.2f}',
                lw=2.5, alpha=.8)

        # Plot standard deviation area
        std_tpr = np.std(tprs, axis=0)
        tprs_upper = np.minimum(mean_tpr + std_tpr, 1)
        tprs_lower = np.maximum(mean_tpr - std_tpr, 0)
        ax.fill_between(mean_fpr, tprs_lower, tprs_upper, color='grey', alpha=.2)

        # Plot diagonal reference line
        ax.plot([0, 1], [0, 1], linestyle='--', lw=2.5, color='navy',
                alpha=.8)
        
        # Set labels and title
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        if self.cv_method == 'loo':
            ax.set_title(f'Leave-One-Out Cross-Validated Mean ROC Curve +/- SD')
        else:
            ax.set_title(f'{self.cv_folds}-Fold Cross-Validated Mean ROC Curve +/- SD')
        ax.legend(loc="lower right")

        # Save or show plot
        if save_plot:
            plt.savefig('mean_roc_plot.pdf', dpi=500, bbox_inches='tight')  
        if show_plot:
            plt.show()
        else:
            plt.close(fig)

        # Print results
        print(f"AUC of mean ROC: {mean_auc:.2f}")
        print(f"Average of individual AUCs: {avg_auc:.2f} ± {std_auc:.2f}")

        return mean_auc
    
    ## For class imbalance use repeated downsampling cv
    def repeated_cv_with_visualization(self, X, y, n_repeats=10, show_plot=True, save_plot=False, 
                                   show_individual_curves=False):
        """
        Perform repeated cross-validation with different random downsampling.
        Simplified visualization focusing on the mean results.
        
        Parameters:
        -----------
        X, y : Input features and target
        n_repeats : Number of CV repeats with different downsampling
        show_plot : Whether to display the plot
        save_plot : Whether to save the plot
        show_individual_curves : Whether to show each repeat's ROC curve (False for cleaner plot)
        """
        # Convert inputs to numpy arrays if needed
        if isinstance(X, pd.DataFrame) or isinstance(X, pd.Series):
            X = X.values
        if isinstance(y, pd.DataFrame) or isinstance(y, pd.Series):
            y = y.values.ravel()
        
        # Storage for results
        all_tprs = []  # All TPR curves from all folds of all repeats
        all_aucs = []  # All AUC values from all folds of all repeats
        repeat_mean_aucs = []  # Mean AUC for each repeat
        
        # Common FPR points for interpolation
        mean_fpr = np.linspace(0, 1, 100)
        
        # Create figure for ROC curve
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        
        # Color map for different repeats (if showing individual curves)
        colors = plt.cm.jet(np.linspace(0, 1, n_repeats))
        
        for i in range(n_repeats):
            # Use different random seed for each repetition
            random_seed = 42 + i
            
            # Storage for this repeat
            repeat_tprs = []
            repeat_aucs = []
            
            # Setup cross-validation
            if self.cv_method == 'loo':
                cv = LeaveOneOut()
            else:
                cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=random_seed)
            
            # Run CV with this random seed
            for train_idx, test_idx in cv.split(X, y):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]
                
                # Skip if test set has only one class
                if len(np.unique(y_test)) < 2:
                    continue
                
                # Process training data with this repeat's random seed
                if self.downsample_ratio is not None:
                    X_train_downsampled, y_train_downsampled = self.balance_classes(
                        X_train, y_train, random_state=random_seed
                    )
                else:
                    X_train_downsampled, y_train_downsampled = X_train, y_train
                
                # Apply log transform and scaling 
                X_train_log = np.log1p(X_train_downsampled)
                self.scaler.fit(X_train_log)
                X_train_scaled = self.scaler.transform(X_train_log)
                
                # Process test data (no downsampling)
                X_test_log = np.log1p(X_test)
                X_test_scaled = self.scaler.transform(X_test_log)
                
                # Encode training labels
                if self.one_hot_encode:
                    y_train_encoded = self.one_hot_encoder.fit_transform(y_train_downsampled.reshape(-1, 1))
                else:
                    y_train_encoded = self.label_encoder.fit_transform(y_train_downsampled)
                
                # Fit model on processed training data
                self.pls_da.fit(X_train_scaled, y_train_encoded)
                
                # Predict on test data
                y_score = self.pls_da.predict(X_test_scaled).ravel()
                
                # Calculate ROC
                fpr, tpr, _ = roc_curve(y_test, y_score)
                
                # Handle interpolation
                if len(fpr) > 1:
                    interp_tpr = np.interp(mean_fpr, fpr, tpr)
                    interp_tpr[0] = 0.0
                    interp_tpr[-1] = 1.0
                else:
                    interp_tpr = np.zeros_like(mean_fpr)
                    interp_tpr[mean_fpr >= fpr[0]] = 1.0
                
                fold_auc = auc(fpr, tpr)
                
                # Store results
                repeat_tprs.append(interp_tpr)
                repeat_aucs.append(fold_auc)
                all_tprs.append(interp_tpr)
                all_aucs.append(fold_auc)
            
            # Calculate mean ROC for this repeat
            if repeat_tprs:
                mean_tpr = np.mean(repeat_tprs, axis=0)
                repeat_auc = np.mean(repeat_aucs)
                repeat_mean_aucs.append(repeat_auc)
                
                # Plot mean ROC for this repeat (only if requested)
                if show_individual_curves:
                    label = f'Repeat {i+1} (AUC = {repeat_auc:.2f})'
                    ax1.plot(mean_fpr, mean_tpr, color=colors[i], alpha=0.15, lw=1)  # Very light!
        
        # Calculate overall mean ROC across all repeats
        if all_tprs:
            mean_tpr = np.mean(all_tprs, axis=0)
            mean_tpr[0] = 0.0
            mean_tpr[-1] = 1.0
            mean_auc = np.mean(all_aucs)
            std_auc = np.std(all_aucs)
            
            # Plot overall mean ROC (more prominent)
            ax1.plot(mean_fpr, mean_tpr, color='darkorange', 
                    label=f'ROC AUC = {mean_auc:.2f} ± {std_auc:.2f}',
                    lw=2.5, alpha=.8)
            
            # No shaded confidence interval - as per your request
            
        # Plot diagonal reference line
        ax1.plot([0, 1], [0, 1], 'k--', lw=1.5)
        
        # Configure ROC subplot
        ax1.set_xlim([-0.05, 1.05])
        ax1.set_ylim([-0.05, 1.05])
        ax1.set_xlabel('False Positive Rate')
        ax1.set_ylabel('True Positive Rate')
        #ax1.set_title(f'{self.cv_folds}-Fold Cross-Validated Mean ROC Curve +/- SD')
        ax1.legend(loc="lower right")
        
        # Create a separate figure for boxplot of AUC values
        if repeat_mean_aucs:
            fig2, ax2 = plt.subplots(figsize=(6, 6))
            ax2.boxplot(repeat_mean_aucs, patch_artist=True, 
                    boxprops=dict(facecolor='lightblue'))
            ax2.axhline(y=mean_auc, color='r', linestyle='-', label=f'Mean: {mean_auc:.2f}')
            
            # Add individual points as a swarm plot
            x_jitter = np.random.normal(1, 0.04, size=len(repeat_mean_aucs))
            ax2.scatter(x_jitter, repeat_mean_aucs, c='navy', alpha=0.6)
            
            # Configure boxplot subplot
            ax2.set_ylabel('AUC')
            ax2.set_title('Distribution of AUC Values\nacross Repeats')
            ax2.set_ylim([min(0.5, min(repeat_mean_aucs)-0.05), 1.05])
            ax2.set_xticks([])
            ax2.set_xticklabels([])
            ax2.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # Save or show plot
        if save_plot:
            fig1.savefig('repeated_cv_roc_plot.pdf', dpi=300, bbox_inches='tight')
            if repeat_mean_aucs:
                fig2.savefig('repeated_cv_auc_boxplot.pdf', dpi=300, bbox_inches='tight')
        if show_plot:
            plt.show()
        else:
            plt.close(fig1)
            if repeat_mean_aucs:
                plt.close(fig2)
        
        # Calculate and print overall statistics
        if repeat_mean_aucs:
            mean_repeat_auc = np.mean(repeat_mean_aucs)
            std_repeat_auc = np.std(repeat_mean_aucs)
            
            print(f"Repeated CV Results ({n_repeats} repeats):")
            print(f"Mean AUC: {mean_repeat_auc:.3f} ± {std_repeat_auc:.3f}")
            print(f"Range: [{min(repeat_mean_aucs):.3f}, {max(repeat_mean_aucs):.3f}]")
            
            return mean_repeat_auc, std_repeat_auc
        else:
            print("Unable to calculate statistics. No valid results found.")
            return None, None



    # repeated VIP impact analysis 
    def compute_repeated_vip(self, X, y, feature_names, n_repeats=10):
        """
        Compute VIP scores across multiple downsampling iterations.
        
        Parameters:
        -----------
        X : array-like
            Features
        y : array-like
            Labels
        feature_names : list
            Names of features
        n_repeats : int
            Number of downsampling repeats
            
        Returns:
        --------
        tuple
            (mean_vip_scores, std_vip_scores, mean_signed_vip, std_signed_vip)
        """
        # Convert inputs to numpy arrays if needed
        if isinstance(X, pd.DataFrame):
            feature_names = X.columns.tolist()
            X = X.values
        if isinstance(y, pd.DataFrame) or isinstance(y, pd.Series):
            y = y.values.ravel()
        
        # Get sign direction from full dataset (for consistency)
        lr = LogisticRegression(max_iter=2000).fit(X, y)
        global_signs = np.sign(lr.coef_[0])
        
        # Storage for all VIP scores across repeats
        all_vip_scores = []
        all_signed_vip = []
        
        for i in range(n_repeats):
            # Use different random seed for each repetition
            random_seed = 42 + i
            np.random.seed(random_seed)
            
            # Downsample if needed
            if self.downsample_ratio is not None:
                X_downsampled, y_downsampled = self.balance_classes(X, y, random_state=random_seed)
            else:
                X_downsampled, y_downsampled = X, y
            
            # Preprocess downsampled data
            X_processed, y_processed = self.preprocess(X_downsampled, y_downsampled)
            y_encoded = self.encode_labels(y_processed)
            
            # Fit PLS model on this repeat's data
            self.pls_da.fit(X_processed, y_encoded)
            
            # Calculate VIP scores for this repeat
            vip_scores = self.compute_vip()
            signed_vip = vip_scores * global_signs  # Use consistent signs
            
            # Store results
            all_vip_scores.append(vip_scores)
            all_signed_vip.append(signed_vip)
        
        # Convert to numpy arrays
        all_vip_scores = np.array(all_vip_scores)
        all_signed_vip = np.array(all_signed_vip)
        
        # Calculate statistics
        mean_vip = np.mean(all_vip_scores, axis=0)
        std_vip = np.std(all_vip_scores, axis=0)
        mean_signed_vip = np.mean(all_signed_vip, axis=0)
        std_signed_vip = np.std(all_signed_vip, axis=0)
        
        return mean_vip, std_vip, mean_signed_vip, std_signed_vip, feature_names

    def plot_repeated_vip(self, X, y, feature_names=None, n_repeats=10, 
                        colors=['darkslategray', 'darkorange'], 
                        custom_order=None, show_plot=True, save_plot=False):
        """
        Calculate and plot VIP scores with error bars from repeated downsampling.
        
        Parameters:
        -----------
        X : array-like
            Features
        y : array-like
            Labels
        feature_names : list, optional
            Names of features (will use X.columns if X is DataFrame)
        n_repeats : int
            Number of downsampling repeats
        colors : list
            Two colors for negative and positive scores
        custom_order : list, optional
            Custom ordering of features
        """
        # Get feature names from DataFrame if available
        if feature_names is None and isinstance(X, pd.DataFrame):
            feature_names = X.columns.tolist()
        
        # Compute VIP scores with repeats
        mean_vip, std_vip, mean_signed_vip, std_signed_vip, feature_names = self.compute_repeated_vip(
            X, y, feature_names, n_repeats
        )
        
        # Handle custom ordering
        if custom_order is not None:
            # Verify all features are in custom_order
            if not all(feat in custom_order for feat in feature_names):
                raise ValueError("custom_order must contain all feature names")
            
            # Create mappings
            score_dict = dict(zip(feature_names, mean_signed_vip))
            std_dict = dict(zip(feature_names, std_signed_vip))
            
            # Use custom order
            sorted_feature_names = custom_order
            sorted_vip_scores = [score_dict[feat] for feat in custom_order]
            sorted_vip_stds = [std_dict[feat] for feat in custom_order]
        else:
            # RESTORED ORIGINAL SORTING LOGIC:
            # Group negatives and positives, then sort within each group
            positive_indices = [i for i, score in enumerate(mean_signed_vip) if score >= 0]
            negative_indices = [i for i, score in enumerate(mean_signed_vip) if score < 0]

            positive_sorted = sorted([(mean_signed_vip[i], std_signed_vip[i], feature_names[i]) 
                                    for i in positive_indices], key=lambda x: x[0], reverse=True)
            negative_sorted = sorted([(mean_signed_vip[i], std_signed_vip[i], feature_names[i]) 
                                    for i in negative_indices], key=lambda x: x[0])

            sorted_vip_scores = [score for score, _, _ in negative_sorted + positive_sorted]
            sorted_vip_stds = [std for _, std, _ in negative_sorted + positive_sorted]
            sorted_feature_names = [name for _, _, name in negative_sorted + positive_sorted]
        
        
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Determine bar colors
        bar_colors = [colors[0] if score < 0 else colors[1] for score in sorted_vip_scores]
        
        # Create horizontal bar plot with error bars
        y_pos = np.arange(len(sorted_feature_names))
        bars = ax.barh(y_pos, sorted_vip_scores, xerr=sorted_vip_stds, 
                    color=bar_colors, edgecolor='black', linewidth=1.8,
                    error_kw=dict(ecolor='black', capsize=3, elinewidth=1.5))
        
        # Set y-ticks and labels
        ax.set_yticks(y_pos)
        ax.set_yticklabels(sorted_feature_names)
        
        # Invert y-axis to have highest absolute values at top
        ax.invert_yaxis()
        
        # Center the plot on 0
        max_pos_limit = max([score + std for score, std in zip(sorted_vip_scores, sorted_vip_stds)])
        min_neg_limit = min([score - std for score, std in zip(sorted_vip_scores, sorted_vip_stds)])
        max_abs_vip = max(abs(max_pos_limit), abs(min_neg_limit)) * 1.1  # Add 10% margin
        
        ax.set_xlim(-max_abs_vip, max_abs_vip)
        
        # Add reference lines
        ax.axvline(x=-1, color='r', linestyle='--', linewidth=1.8)
        ax.axvline(x=0, color='k', linestyle='--', linewidth=1.2)
        ax.axvline(x=1, color='r', linestyle='--', linewidth=1.8)
        
        # Add titles and labels
        ax.set_xlabel('VIP Score (with std. dev across repeats)')
        ax.set_ylabel('Features')
        #ax.set_title(f'Variable Importance from {n_repeats} Repeated Downsampling Runs')
        
        # Add a note about the repeats
        # plt.figtext(0.5, 0.01, 
        #         f'Error bars show standard deviation across {n_repeats} different downsampling instances', 
        #         ha='center', fontsize=9, fontstyle='italic')
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        
        if save_plot:
            plt.savefig('repeated_vip_scores.pdf', dpi=500, bbox_inches='tight')
        
        if show_plot:
            plt.show()
        else:
            plt.close(fig)
        
        return mean_signed_vip, std_signed_vip, sorted_feature_names
    
     #new function to do some bootstrap analysis on the VIP scores (not needed for class imbalance)
    def bootstrap_vip_analysis(self, X, y, n_bootstraps=100, random_seed=42):
        """
        Perform bootstrap analysis of VIP scores to assess stability.
        
        Parameters:
        -----------
        X : DataFrame or array
            Feature matrix
        y : Series or array
            Target variable
        n_bootstraps : int
            Number of bootstrap samples to generate
        random_seed : int
            Random seed for reproducibility
            
        Returns:
        --------
        dict
            Dictionary with bootstrap results including mean VIP scores,
            standard deviations, and confidence intervals
        """
    
        
        # Convert to numpy if needed
        if hasattr(X, 'values'):
            X_data = X.values
        else:
            X_data = X
            
        if hasattr(y, 'values'):
            y_data = y.values
        else:
            y_data = y
        
        # Get feature names
        feature_names = X.columns.tolist() if hasattr(X, 'columns') else [f"Feature_{i}" for i in range(X_data.shape[1])]
        n_features = len(feature_names)
        
        # Storage for bootstrap results
        all_vip_scores = []
        
        for i in range(n_bootstraps):
            # Set different seed for each bootstrap
            boot_seed = random_seed + i
            np.random.seed(boot_seed)
            
            # Generate bootstrap sample (sampling with replacement)
            indices = np.random.choice(len(y_data), size=len(y_data), replace=True)
            X_boot = X_data[indices]
            y_boot = y_data[indices]
            
            # Preprocess data
            X_scaled, y_processed = self.preprocess(X_boot, y_boot)
            y_encoded = self.encode_labels(y_processed)
            
            # Fit PLS model on bootstrap sample
            self.pls_da.fit(X_scaled, y_encoded)
            
            # Calculate VIP scores
            vip_scores = self.compute_vip()
            all_vip_scores.append(vip_scores)
        
        # Convert to numpy array
        all_vip_scores = np.array(all_vip_scores)
        
        # Calculate statistics
        mean_vip = np.mean(all_vip_scores, axis=0)
        std_vip = np.std(all_vip_scores, axis=0)
        
        # Calculate confidence intervals (95% CI)
        lower_ci = np.percentile(all_vip_scores, 2.5, axis=0)
        upper_ci = np.percentile(all_vip_scores, 97.5, axis=0)
        
        # Get sign direction for each feature
        lr = LogisticRegression(max_iter=2000).fit(X_data, y_data)
        global_signs = np.sign(lr.coef_[0])
        signed_mean_vip = mean_vip * global_signs
        
        # Calculate bootstrap ratio (mean/std) to assess stability
        bootstrap_ratio = mean_vip / (std_vip + 1e-10)  # Add small constant to avoid division by zero
        
        # Calculate how often each feature's VIP exceeds 1.0 (importance threshold)
        vip_significance = np.mean(all_vip_scores >= 1.0, axis=0)
        
        # Create results dictionary
        results = {
            'feature_names': feature_names,
            'mean_vip': mean_vip,
            'std_vip': std_vip,
            'signed_mean_vip': signed_mean_vip,
            'lower_ci': lower_ci,
            'upper_ci': upper_ci,
            'bootstrap_ratio': bootstrap_ratio, 
            'vip_significance': vip_significance,
            'bootstrap_samples': all_vip_scores
        }
        
        return results
    # plot the results of the bootstrap analysis
    def plot_bootstrap_vip(self, bootstrap_results, focus_feature=None, 
                       colors=['darkslategray', 'darkorange'], 
                       sort_by='absolute', save_plot=False):
        """
        Plot the results of bootstrap VIP analysis.
        
        Parameters:
        -----------
        bootstrap_results : dict
            Results from bootstrap_vip_analysis
        focus_feature : str, optional
            Feature to highlight in the plot
        colors : list
            Two colors for negative and positive VIP scores
        sort_by : str
            How to sort features ('absolute', 'value', or 'name')
        save_plot : bool
            Whether to save the plot to a file
        """
        features = bootstrap_results['feature_names']
        mean_vips = bootstrap_results['signed_mean_vip']
        std_vips = bootstrap_results['std_vip']
        lower_ci = bootstrap_results['lower_ci'] * np.sign(mean_vips)  # Apply sign to CI
        upper_ci = bootstrap_results['upper_ci'] * np.sign(mean_vips)  # Apply sign to CI
        
        # Calculate error bars for plotting
        # For symmetric error bars: yerr=std_vips
        # For asymmetric CI: yerr=[mean_vips-lower_ci, upper_ci-mean_vips]
        yerr = std_vips
        
        # Sort features based on specified method
        if sort_by == 'absolute':
            sort_idx = np.argsort(np.abs(mean_vips))
        elif sort_by == 'value':
            sort_idx = np.argsort(mean_vips)
        else:  # sort_by == 'name'
            sort_idx = np.argsort(features)
        
        sorted_features = [features[i] for i in sort_idx]
        sorted_vips = mean_vips[sort_idx]
        sorted_yerr = yerr[sort_idx]
        
        # Create figure
        plt.figure(figsize=(10, max(8, len(sorted_features) * 0.3)))
        
        # Determine bar colors based on sign
        bar_colors = [colors[0] if v < 0 else colors[1] for v in sorted_vips]
        
        # Highlight focus feature if specified
        if focus_feature is not None:
            for i, feature in enumerate(sorted_features):
                if feature == focus_feature:
                    bar_colors[i] = 'red'  # Change color for focus feature
                    break
        
        # Create horizontal bar plot with error bars
        bars = plt.barh(sorted_features, sorted_vips, xerr=sorted_yerr, 
                        color=bar_colors, edgecolor='black', linewidth=1.0,
                        error_kw=dict(ecolor='black', capsize=3, elinewidth=1))
        
        # Add vertical reference lines
        plt.axvline(x=0, color='black', linestyle='--', alpha=0.7)
        plt.axvline(x=1, color='red', linestyle='--', alpha=0.7)
        plt.axvline(x=-1, color='red', linestyle='--', alpha=0.7)
        
        # Add labels and title
        plt.xlabel('Signed VIP Score (with std. dev.)')
        plt.ylabel('Features')
        plt.title('Bootstrap Analysis of VIP Scores')
        
        # Add text about bootstrap iterations
        plt.figtext(0.5, 0.01, 
                    f'Results based on {bootstrap_results["bootstrap_samples"].shape[0]} bootstrap iterations',
                    ha='center', fontsize=9, fontstyle='italic')
        
        # Adjust layout
        plt.tight_layout(rect=[0, 0.03, 1, 0.98])
        
        # Save plot if requested
        if save_plot:
            plt.savefig('bootstrap_vip_analysis.pdf', dpi=300, bbox_inches='tight')
        
        plt.show()
        
        # Also display table with key statistics for each feature
        from IPython.display import display
        import pandas as pd
        
        # Create summary table
        summary_df = pd.DataFrame({
            'Feature': features,
            'Mean VIP': bootstrap_results['mean_vip'],
            'Std Dev': bootstrap_results['std_vip'],
            'Sign': np.sign(bootstrap_results['signed_mean_vip']),
            'VIP >= 1 (%)': bootstrap_results['vip_significance'] * 100,
            'Bootstrap Ratio': bootstrap_results['bootstrap_ratio']
        })
        
        # Sort table same as plot
        summary_df = summary_df.iloc[sort_idx].reset_index(drop=True)
        
        # Highlight focus feature if specified
        if focus_feature is not None:
            summary_df = summary_df.style.apply(
                lambda x: ['background-color: yellow' if val == focus_feature else '' 
                        for val in x], axis=1, subset=['Feature'])
        
        display(summary_df)
        
        return summary_df
        # making predictions with the model
    def analyze_vip_impact(self, X, y, feature_names, features_to_modify=None, modification_type='zero', 
                     scaling_factor=1.0, show_plot=True, show_threshold_plots=True, plot_type='bar', save_plot=False):
        """
        Analyze and visualize the impact of zeroing out features on class predictions.
        
        Parameters:
        ----------
        X : pandas.DataFrame
            Features dataframe.
        y : array-like
            True class labels.
        feature_names : list or pandas.Index
            List of feature names.
        features_to_modify : list, default=None
            List of feature names to modify.
        modification_type : str, default='zero'
            Type of modification to apply. Options: 'zero', 'min', 'max', 'scale_min', 'scale_max'.
        scaling_factor : float, default=1.0
            Factor to use for scaling if modification_type is 'scale_min' or 'scale_max'.
        show_plot : bool, default=True
            Whether to display the pie charts.
        show_threshold_plots : bool, default=True
            Whether to display the threshold selection visualization plots.
        plot_type : str, default='bar'
            Type of plot to generate. Options: 'pie' (original), 'bar' (stacked bar chart).
        
        Returns:
        -------
        dict
            Dictionary containing analysis results.
        """
        from sklearn.metrics import roc_curve, roc_auc_score
        
        print("\n" + "="*50)
        print("STARTING VIP IMPACT ANALYSIS")
        print("="*50)
        
        # Get original class distribution from true labels
        orig_counts = np.bincount(y, minlength=2)
        
        # Get predictions on original data
        X_scaled = self.preprocess_transform(X)
        y_orig_pred = self.pls_da.predict(X_scaled).ravel()
        
        print("\n" + "-"*30)
        print("PREDICTION VALUES BEFORE THRESHOLDING:")
        print("-"*30)
        print("Original predictions:")
        print(f"Min: {y_orig_pred.min():.3f}")
        print(f"Max: {y_orig_pred.max():.3f}")
        print(f"Mean: {y_orig_pred.mean():.3f}")
        print(f"Median: {np.median(y_orig_pred):.3f}")
        
        # Determine threshold from ROC curve
        fpr, tpr, thresholds = roc_curve(y, y_orig_pred)
        optimal_idx = np.argmax(tpr - fpr)
        optimal_threshold = thresholds[optimal_idx]
        
        print("\n" + "-"*30)
        print("ROC CURVE THRESHOLDS:")
        print("-"*30)
        print(f"Min threshold: {thresholds.min():.3f}")
        print(f"Max threshold: {thresholds.max():.3f}")
        print(f"Optimal threshold: {optimal_threshold:.3f}")
        
        # Get predictions using optimal threshold
        original_pred_classes = (y_orig_pred > optimal_threshold).astype(int)
        pred_orig_counts = np.bincount(original_pred_classes, minlength=2)
        
        # Create modified data for each feature progressively
        feature_results = []
        
        # Start with predictions on original data
        feature_results.append({
            'name': 'JUND KD',
            'counts': pred_orig_counts,
            'props': [pred_orig_counts[0]/len(y)*100, pred_orig_counts[1]/len(y)*100]
        })
        
        # For storing intermediate results if needed
        all_modified_results = []
        
        # Process one feature at a time for progressive modifications
        if features_to_modify:
            current_X = X.copy()
            for i, feature in enumerate(features_to_modify):
                # Make a copy of the current working dataset
                X_modified = current_X.copy()
                
                # Get feature index
                feature_idx = -1
                for j, name in enumerate(feature_names):
                    if name == feature:
                        feature_idx = j
                        break
                
                if feature_idx == -1:
                    print(f"Warning: Feature '{feature}' not found in feature_names.")
                    continue
                    
                # Apply modification to this feature
                if modification_type == 'zero':
                    X_modified.iloc[:, feature_idx] = 0
                    # If this is the first feature, show just this feature
                    if i == 0:
                        label = f"{feature} = 0"
                    else:
                        # For subsequent features, show accumulated modified features
                        modified_features = [features_to_modify[j] for j in range(i+1)]
                        label = f"{' & '.join(modified_features)} = 0"
                elif modification_type == 'min':
                    X_modified.iloc[:, feature_idx] = X.iloc[:, feature_idx].min()
                    if i == 0:
                        label = f"{feature} = min"
                    else:
                        modified_features = [features_to_modify[j] for j in range(i+1)]
                        label = f"{' & '.join(modified_features)} = min"
                elif modification_type == 'max':
                    X_modified.iloc[:, feature_idx] = X.iloc[:, feature_idx].max()
                    if i == 0:
                        label = f"{feature} = max"
                    else:
                        modified_features = [features_to_modify[j] for j in range(i+1)]
                        label = f"{' & '.join(modified_features)} = max"
                elif modification_type == 'scale_min':
                    min_val = X.iloc[:, feature_idx].min()
                    X_modified.iloc[:, feature_idx] = min_val * scaling_factor
                    if i == 0:
                        label = f"{feature} = {scaling_factor}x min"
                    else:
                        modified_features = [features_to_modify[j] for j in range(i+1)]
                        label = f"{' & '.join(modified_features)} = {scaling_factor}x min"
                elif modification_type == 'scale_max':
                    max_val = X.iloc[:, feature_idx].max()
                    X_modified.iloc[:, feature_idx] = max_val * scaling_factor
                    if i == 0:
                        label = f"{feature} = {scaling_factor}x max"
                    else:
                        modified_features = [features_to_modify[j] for j in range(i+1)]
                        label = f"{' & '.join(modified_features)} = {scaling_factor}x max"
                
                # Get predictions on modified data
                X_modified_scaled = self.preprocess_transform(X_modified)
                y_modified = self.pls_da.predict(X_modified_scaled).ravel()
                modified_classes = (y_modified > optimal_threshold).astype(int)
                mod_counts = np.bincount(modified_classes, minlength=2)
                
                # Store results
                feature_results.append({
                    'name': label,
                    'counts': mod_counts,
                    'props': [mod_counts[0]/len(y)*100, mod_counts[1]/len(y)*100]
                })
                
                # Save for final results
                if i == len(features_to_modify) - 1:
                    final_modified_classes = modified_classes
                    final_y_modified = y_modified
                    final_mod_counts = mod_counts
                
                # Update current dataset for progressive modification
                current_X = X_modified
                
                # Store all intermediate results
                all_modified_results.append({
                    'feature': feature,
                    'modified_classes': modified_classes,
                    'y_modified': y_modified,
                    'mod_counts': mod_counts
                })
        
        # Get the final modified predictions for the return value
        if all_modified_results:
            # Use the last modification as the final result
            modified_classes = final_modified_classes
            y_modified = final_y_modified
            mod_counts = final_mod_counts
        else:
            # If no modifications, use original
            modified_classes = original_pred_classes
            y_modified = y_orig_pred
            mod_counts = pred_orig_counts
        
        print("\n" + "-"*30)
        print("MODIFIED DATA PREDICTIONS:")
        print("-"*30)
        print(f"Min: {y_modified.min():.3f}")
        print(f"Max: {y_modified.max():.3f}")
        print(f"Mean: {y_modified.mean():.3f}")
        print(f"Median: {np.median(y_modified):.3f}")
        
        # Calculate how many samples changed prediction
        changes = np.sum(original_pred_classes != modified_classes)

        # Display threshold selection visualization if requested
        if show_threshold_plots:
            self.plot_threshold_selection(y, y_orig_pred, fpr, tpr, thresholds, optimal_idx)
            self.plot_score_distribution(y, y_orig_pred, optimal_threshold)
        
        if show_plot:
            if plot_type == 'pie':
                # Original pie chart plotting code
                fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))
                wedgeprops = dict(width=0.5, edgecolor='white', linewidth=1.5)
                
                # Calculate proportions
                orig_props = [orig_counts[0]/len(y)*100, 
                            orig_counts[1]/len(y)*100]
                pred_orig_props = [pred_orig_counts[0]/len(y)*100,
                                pred_orig_counts[1]/len(y)*100]
                mod_props = [mod_counts[0]/len(modified_classes)*100,
                            mod_counts[1]/len(modified_classes)*100]
                
                print("\nDEBUG - Values being plotted:")
                print(f"True distribution props: {orig_props}")
                print(f"Original prediction props: {pred_orig_props}")
                print(f"Modified prediction props: {mod_props}")
                mod_description = {
                    'zero': 'Zeroing',
                    'min': 'Minimizing',
                    'max': 'Maximizing',
                    'scale_min': f'Scaling Min by {scaling_factor}x',
                    'scale_max': f'Scaling Max by {scaling_factor}x'
                }
                
                # True distribution donut chart
                ax1.pie(orig_props, labels=['FRA2 low', 'FRA2 high'],
                        colors=['darkslategray', 'darkorange'],
                        autopct='%1.1f%%', startangle=90,
                        pctdistance=0.85,
                        wedgeprops=wedgeprops)
                ax1.set_title('True Class Distribution')
                
                # Original predictions donut chart
                ax2.pie(pred_orig_props, labels=['FRA2 low', 'FRA2 high'],
                        colors=['darkslategray', 'darkorange'],
                        autopct='%1.1f%%', startangle=90,
                        pctdistance=0.85,
                        wedgeprops=wedgeprops)
                ax2.set_title('Model Predictions\n(Original Data)')
                
                # Modified predictions donut chart
                ax3.pie(mod_props, labels=['FRA2 low', 'FRA2 high'],
                        colors=['darkslategray', 'darkorange'],
                        autopct='%1.1f%%', startangle=90,
                        pctdistance=0.85,
                        wedgeprops=wedgeprops)
                ax3.set_title(f'Model Predictions After\n{mod_description[modification_type]} {features_to_modify}')
            
            elif plot_type == 'bar':
                # Create stacked bar chart
                plt.figure(figsize=(12, 6))
                
                # Extract data for plotting
                conditions = [result['name'] for result in feature_results]
                
                # Format long condition names with newlines
                formatted_conditions = []
                for condition in conditions:
                    if len(condition) > 15 and '&' in condition:
                        # Replace '&' with '\n&' to create a newline
                        formatted_condition = condition.replace(' & ', '\n& ')
                    else:
                        formatted_condition = condition
                    formatted_conditions.append(formatted_condition)
                
                class0_props = [result['props'][0] for result in feature_results]
                class1_props = [result['props'][1] for result in feature_results]
                
                # Create bar positions
                x = np.arange(len(conditions))
                width = 0.5  # Narrower bars (was 0.8)
                
                # Create stacked bars
                plt.bar(x, class0_props, width, label='FRA2 low', color='darkslategray')
                plt.bar(x, class1_props, width, bottom=class0_props, label='FRA2 high', color='darkorange')
                
                # Customize plot
                #plt.xlabel('Feature Modification')
                plt.ylabel('FRA2 percentage (%)')
                #plt.title('Impact of Feature Modifications on Class Predictions')
                plt.xticks(x, formatted_conditions, rotation=45, ha='right')
                
                # Set a reasonable figure height based on the number of newlines
                max_newlines = max([cond.count('\n') for cond in formatted_conditions])
                plt.gcf().set_size_inches(12, 6 + max_newlines * 0.5)
                
                # Move legend outside the plot
                plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                
                # Add percentage labels on bars
                for i, (c0, c1) in enumerate(zip(class0_props, class1_props)):
                    # Class 0 percentage in the middle of its section
                    plt.text(i, c0/2, f'{c0:.1f}%', ha='center', va='center', color='white', fontsize=12,fontweight='bold')
                    # Class 1 percentage in the middle of its section
                    if c1 > 5:  # Only show text if the bar is large enough
                        plt.text(i, c0 + c1/2, f'{c1:.1f}%', ha='center', va='center', color='white', fontsize=12,fontweight='bold')
                
                plt.tight_layout()  # This will adjust layout to account for the legend outside
                
                if save_plot:
                    plt.savefig('FRA2_predictions_impact_on_model.pdf', dpi=300, bbox_inches='tight')
                
            plt.tight_layout()
            
            # Print detailed summary
            print("\nClass Distribution Summary:")
            print("True Labels:")
            true_class0_percent = orig_counts[0]/len(y)*100
            true_class1_percent = orig_counts[1]/len(y)*100
            print(f"FRA2 low: {orig_counts[0]} ({true_class0_percent:.1f}%), FRA2 high: {orig_counts[1]} ({true_class1_percent:.1f}%)")
            
            print("\nOriginal Model Predictions:")
            orig_pred0_percent = pred_orig_counts[0]/len(y)*100
            orig_pred1_percent = pred_orig_counts[1]/len(y)*100
            print(f"FRA2 low: {pred_orig_counts[0]} ({orig_pred0_percent:.1f}%), FRA2 high: {pred_orig_counts[1]} ({orig_pred1_percent:.1f}%)")
            
            print("\nPredictions After Modifying Features:")
            final_mod0_percent = mod_counts[0]/len(modified_classes)*100
            final_mod1_percent = mod_counts[1]/len(modified_classes)*100
            print(f"FRA2 low: {mod_counts[0]} ({final_mod0_percent:.1f}%), FRA2 high: {mod_counts[1]} ({final_mod1_percent:.1f}%)")
            
            print(f"\nSamples that changed prediction: {changes} ({changes/len(y)*100:.1f}%)")
            
            if not show_plot:
                plt.close()
                
        return {
            'original_classes': y,
            'modified_classes': modified_classes,
            'class_changes': changes,
            'orig_class_counts': orig_counts,
            'mod_class_counts': mod_counts,
            'optimal_threshold': optimal_threshold,
            'original_predictions': y_orig_pred,
            'modified_predictions': y_modified,
            'all_modifications': all_modified_results if features_to_modify else None
        }
        
    def plot_threshold_selection(self, y_true, y_pred, fpr, tpr, thresholds, optimal_idx):
        """
        Plot the ROC curve with the optimal threshold point highlighted.
        
        Parameters:
        ----------
        y_true : array-like
            True class labels.
        y_pred : array-like
            Predicted scores.
        fpr : array-like
            False positive rates.
        tpr : array-like
            True positive rates.
        thresholds : array-like
            Thresholds corresponding to FPR and TPR.
        optimal_idx : int
            Index of the optimal threshold.
        """
        from sklearn.metrics import roc_auc_score
        
        # Calculate AUC
        roc_auc = roc_auc_score(y_true, y_pred)
        optimal_threshold = thresholds[optimal_idx]
        
        plt.figure(figsize=(10, 6))
        plt.plot(fpr, tpr, 'b-', label=f'ROC Curve (AUC = {roc_auc:.3f})')
        plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
        plt.plot(fpr[optimal_idx], tpr[optimal_idx], 'ro', markersize=8, 
                label=f'Optimal Threshold = {optimal_threshold:.3f}')
        
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve with Optimal Threshold')
        plt.legend(loc='lower right')
        plt.grid(True, alpha=0.3)
        plt.show()
        
        # Also plot TPR-FPR difference vs thresholds
        plt.figure(figsize=(10, 6))
        difference = tpr - fpr
        
        # If there are too many thresholds, thin them out for better visualization
        if len(thresholds) > 100:
            step = len(thresholds) // 100
            thresholds_plot = thresholds[::step]
            difference_plot = difference[::step]
            # Make sure we include the optimal point regardless of thinning
            if optimal_idx % step != 0:
                thresholds_plot = np.append(thresholds_plot, thresholds[optimal_idx])
                difference_plot = np.append(difference_plot, difference[optimal_idx])
                # Resort to keep order
                sort_idx = np.argsort(thresholds_plot)
                thresholds_plot = thresholds_plot[sort_idx]
                difference_plot = difference_plot[sort_idx]
        else:
            thresholds_plot = thresholds
            difference_plot = difference
        
        plt.plot(thresholds_plot, difference_plot, 'g-')
        plt.plot(optimal_threshold, difference[optimal_idx], 'ro', markersize=8,
                label=f'Optimal Threshold = {optimal_threshold:.3f}')
        
        plt.xlabel('Threshold Value')
        plt.ylabel('TPR - FPR')
        plt.title('Threshold Optimization: Maximizing TPR-FPR Difference')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Add annotation for maximum difference
        plt.annotate(f'Max Difference = {difference[optimal_idx]:.3f}', 
                    xy=(optimal_threshold, difference[optimal_idx]),
                    xytext=(optimal_threshold+0.1, difference[optimal_idx]-0.05),
                    arrowprops=dict(arrowstyle='->'))
        
        plt.show()

    def plot_score_distribution(self, y_true, y_pred, optimal_threshold):
        """
        Plot the distribution of prediction scores by class with the threshold line.
        
        Parameters:
        ----------
        y_true : array-like
            True class labels.
        y_pred : array-like
            Predicted scores.
        optimal_threshold : float
            Optimal classification threshold.
        """
        plt.figure(figsize=(10, 6))
        
        # Get scores for each class
        class0_scores = y_pred[y_true == 0]
        class1_scores = y_pred[y_true == 1]
        
        # Plot histograms
        plt.hist(class0_scores, bins=20, alpha=0.6, color='darkslategray', 
                label=f'FRA2 low (n={len(class0_scores)})')
        plt.hist(class1_scores, bins=20, alpha=0.6, color='darkorange', 
                label=f'FRA2 high (n={len(class1_scores)})')
        
        # Add threshold line
        plt.axvline(x=optimal_threshold, color='r', linestyle='--', linewidth=2,
                label=f'Optimal Threshold = {optimal_threshold:.3f}')
        
        plt.xlabel('Prediction Score')
        plt.ylabel('Frequency')
        plt.title('Distribution of Prediction Scores by Class')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()
    

    def visualize_feature_impacts(self, X, y, feature_names=None, top_n=10, modification_type='scale_max', 
                               scaling_factor=1.5, show_plot=True, save_plot=False):
        """
        Visualize the impact of modifying individual features on class predictions and distribution shifts.
        
        Parameters:
        ----------
        X : pandas.DataFrame
            Features dataframe.
        y : array-like
            True class labels.
        feature_names : list or pandas.Index, default=None
            List of feature names. If None, will use X.columns.
        top_n : int, default=10
            Number of top features to display.
        modification_type : str, default='scale_max'
            Type of modification to apply to features. Options include:
            'zero', 'min', 'max', 'scale_min', 'scale_max'.
        scaling_factor : float, default=1.5
            Factor to use for scaling if modification_type is 'scale_min' or 'scale_max'.
        show_plot : bool, default=True
            Whether to display the plot.
        save_plot : bool, default=False
            Whether to save the plot to a file.
            
        Returns:
        -------
        dict
            Dictionary containing feature impact metrics.
        """

        # Use X.columns if feature_names is None
        if feature_names is None:
            feature_names = X.columns
        
        # Convert feature_names to list if it's a pandas Index
        if hasattr(feature_names, 'tolist'):
            feature_names = feature_names.tolist()
        
        # Get VIP scores to select top features
        vip_scores = self.compute_vip()
        top_features_idx = np.argsort(vip_scores)[-top_n:]
        top_features = [feature_names[i] for i in top_features_idx]
        
        # Get original predictions
        X_scaled = self.preprocess_transform(X)
        y_orig_pred = self.pls_da.predict(X_scaled).ravel()
        
        # Determine threshold from ROC curve
        fpr, tpr, thresholds = roc_curve(y, y_orig_pred)
        optimal_idx = np.argmax(tpr - fpr)
        optimal_threshold = thresholds[optimal_idx]
        
        # Get original class predictions using optimal threshold
        original_pred_classes = (y_orig_pred > optimal_threshold).astype(int)
        original_class1_pct = np.mean(original_pred_classes) * 100
        
        # Dictionary to store results
        results = {
            'feature': [],
            'class1_pct_change': [],
            'original_predictions': y_orig_pred,
            'modified_predictions': {},
            'original_threshold': optimal_threshold,
            'impact_magnitude': []
        }
        
        # Analyze each feature's impact
        for feature in top_features:
            # Get index of the feature
            if hasattr(X, 'columns') and feature in X.columns:
                feature_idx = X.columns.get_loc(feature)
            else:
                feature_idx = feature_names.index(feature)
            
            # Create modified data
            X_modified = X.copy()
            
            # Apply modification based on type
            if modification_type == 'zero':
                X_modified.iloc[:, feature_idx] = 0
            elif modification_type == 'min':
                X_modified.iloc[:, feature_idx] = X.iloc[:, feature_idx].min()
            elif modification_type == 'max':
                X_modified.iloc[:, feature_idx] = X.iloc[:, feature_idx].max()
            elif modification_type == 'scale_min':
                min_val = X.iloc[:, feature_idx].min()
                X_modified.iloc[:, feature_idx] = min_val * scaling_factor
            elif modification_type == 'scale_max':
                max_val = X.iloc[:, feature_idx].max()
                X_modified.iloc[:, feature_idx] = max_val * scaling_factor
            
            # Get predictions for modified data
            X_modified_scaled = self.preprocess_transform(X_modified)
            y_modified = self.pls_da.predict(X_modified_scaled).ravel()
            modified_classes = (y_modified > optimal_threshold).astype(int)
            
            # Calculate percentage of class 1 in modified predictions
            modified_class1_pct = np.mean(modified_classes) * 100
            
            # Calculate change in class 1 percentage
            class1_pct_change = modified_class1_pct - original_class1_pct
            
            # Store results
            results['feature'].append(feature)
            results['class1_pct_change'].append(class1_pct_change)
            results['modified_predictions'][feature] = y_modified
            results['impact_magnitude'].append(abs(class1_pct_change))
        
        # Sort features by absolute impact
        sorted_indices = np.argsort(results['impact_magnitude'])[::-1]
        results['feature'] = [results['feature'][i] for i in sorted_indices]
        results['class1_pct_change'] = [results['class1_pct_change'][i] for i in sorted_indices]
        results['impact_magnitude'] = [results['impact_magnitude'][i] for i in sorted_indices]
        
        # Create plot
        if show_plot:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
            
            # Feature Impact Ranking (subplot 1)
            colors = ['darkslategray' if x < 0 else 'darkorange' for x in results['class1_pct_change']]
            ax1.barh(results['feature'], results['class1_pct_change'], color=colors, edgecolor='black', linewidth=1)
            ax1.axvline(x=0, color='black', linestyle='--')
            ax1.set_xlabel('Change in Class 1 Percentage Points')
            ax1.set_title(f'Feature Impact Ranking ({modification_type}, factor={scaling_factor})')
            ax1.set_ylabel('Features')
            
            # Add a note about interpretation
            mod_description = {
                'zero': 'zeroing',
                'min': 'minimizing',
                'max': 'maximizing',
                'scale_min': f'scaling minimum by {scaling_factor}x',
                'scale_max': f'scaling maximum by {scaling_factor}x'
            }
            
            # Distribution Shifts (subplot 2)
            # Choose top 3 features by impact for distribution plot
            top3_features = results['feature'][:3]
            
            ax2.hist(y_orig_pred, bins=30, alpha=0.5, color='gray', label='JUND KD')
            ax2.axvline(x=optimal_threshold, color='black', linestyle='--', label='Threshold')
            
            colors = ['red', 'blue', 'green']
            for i, feature in enumerate(top3_features):
                ax2.hist(results['modified_predictions'][feature], bins=30, alpha=0.3, color=colors[i], label=f'Modified {feature}')
            
            ax2.set_xlabel('Model Prediction Values')
            ax2.set_ylabel('Frequency')
            ax2.set_title('Distribution of Prediction Values Before/After Feature Modification')
            ax2.legend()
            
            plt.tight_layout()
            
            if save_plot:
                plt.savefig('feature_impact_analysis.pdf', dpi=300, bbox_inches='tight')
            
            if not show_plot:
                plt.close(fig)
            
        return results