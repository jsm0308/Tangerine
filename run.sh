cd /Seraph/상/레포/Tangerine 경로   # 실제 절대경로
source "$HOME/miniconda3/etc/profile.d/conda.sh"  # 서버 conda 경로에 맞게
conda activate tangerine
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0
python scripts/build_glb_from_2d.py --config Generate_Tangerine_3D/from_2d_track/configs/from_2d_batch.yamlㅋ`