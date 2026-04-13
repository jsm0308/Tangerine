# Seraph ↔ 로컬 — 코드 올리기·내리기·실행

GitHub(`origin`)를 가운데 두고 **로컬 PC**와 **Seraph**가 같은 레포를 쓰는 방식이다.

---

## 1. 로컬에서 고친 코드 → Seraph에 반영 (올리기)

**로컬 (Windows, 프로젝트 폴더에서):**

```text
git add -A
git commit -m "메시지"
git push origin main
```

**Seraph (SSH 접속 후):**

```bash
cd /data/minjae051213/Tangerine
git pull origin main
```

이제 Seraph 쪽 코드가 로컬에서 방금 올린 커밋과 같다.

---

## 2. Seraph에서 고친 코드 → 로컬로 가져오기 (내리기)

**Seraph에서 커밋까지 한 경우:**

```bash
cd /data/minjae051213/Tangerine
git add -A
git commit -m "메시지"
git push origin main
```

**로컬에서:**

```text
git pull origin main
```

---

## 3. Git 없이 파일만 복사 (선택)

- **로컬 → Seraph:** PowerShell 등에서 `scp -P 30080 -r 경로 minjae051213@aurora.khu.ac.kr:/data/minjae051213/Tangerine/`
- **Seraph → 로컬:** `scp -P 30080 minjae051213@aurora.khu.ac.kr:/data/.../파일 로컬경로`

(포트·호스트는 `local/ssh_config_snippet_aurora_seraph.txt` 와 동일.)

---

## 4. Seraph에서 코드 실행 (예: 컨베이어)

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate tangerine
cd /data/minjae051213/Tangerine
git pull

python scripts/run_conveyor_demo.py --out outputs/conveyor_demo --frames 200 --cycles 8
```

Blender 경로가 필요하면 `--blender /절대/경로/blender` 추가.

---

## 5. 한 줄 요약

| 하고 싶은 것 | 할 일 |
|--------------|--------|
| 로컬 수정 → Seraph | 로컬 `git push` → Seraph `git pull` |
| Seraph 수정 → 로컬 | Seraph `git push` → 로컬 `git pull` |
| 실행 | Seraph에서 `conda activate` → `cd Tangerine` → `python ...` |
