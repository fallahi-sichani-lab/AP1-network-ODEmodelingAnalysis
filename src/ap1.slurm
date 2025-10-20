#!/bin/bash
#SBATCH -A rivanna_fallahi_lab
#SBATCH -p standard
#SBATCH -c 40
#SBATCH -t 24:00:00
#SBATCH --mem=360GB

module purge
module load goolf/11.4.0_4.1.4
module load anaconda

source activate ap1_proj_py311
DIR=~/.conda/envs/ap1_proj_py311
export PATH=$DIR/bin:$PATH
export LD_LIBRARY_PATH=$DIR/bin:$LD_LIBRARY_PATH
export PYTHONPATH=$DIR/bin:$PYTHONPATH
export SLURM_NPROCS=${SLURM_CPUS_PER_TASK}

BASE_DIR=/scratch/njr7jk/100825_sims

which python
python run_simulation.py $BASE_DIR
