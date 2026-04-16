#!/bin/bash
#SBATCH -p batch_ugrad        # 사용할 파티션
#SBATCH --account=[내_어카운트] # 필수: sshare -U minjae051213 로 확인한 이름
#SBATCH --gres=gpu:1          # GPU 개수
#SBATCH -o result.out         # 결과가 저장될 파일명

# 내 파이썬 코드 실행
python train_tangerine_2d.py