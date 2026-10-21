# Sample 생산 레시피

`DeepMuonRecoSample`의 Slurm 제출 스크립트를 호출한다. 저장소 루트에서 실행한다.
Run3 ntuple과 Data에는 `bash ../DeepMuonRecoSample/Run3/setup_cmssw.sh`,
Phase2에는 `bash ../DeepMuonRecoSample/Phase2/setup_cmssw.sh`를 한 번 실행한다.
Data 제출 전에는 `voms-setup`으로 프록시를 갱신한다.

Run3 MC의 GEN-SIM과 MinBias는 함께 제출할 수 있다. 둘 다 완성되면
premix부터 각 단계의 결과를 확인한 뒤 다음 단계를 실행한다.

```bash
bash runs/sample/run3_mc.sh gensim
bash runs/sample/run3_mc.sh minbias
bash runs/sample/run3_mc.sh premix
bash runs/sample/run3_mc.sh digiraw
bash runs/sample/run3_mc.sh reco
bash runs/sample/run3_mc.sh ntuple
```

`gensim` 249개와 `minbias` 2490개를 제출한다. Run3 MC 결과는 모두
`~/workspace/.store/deepmuonreco/chunk/sim-run3-singlemu-v001/` 아래에 저장한다.
단계별 ROOT 파일은 `gensim/`, `minbias/`, `premix/`, `digiraw/`, `reco/`,
`ntuple/`에, 로그는 `logs/<stage>/`에 둔다. 시험 결과와 로그는 같은 경로의 `test/`에 둔다.
Run3 MC와 Data의 각 단계 ROOT 파일명은 `output_0.root`, `output_1.root`, …이다.

MC ntuple 249개가 모두 완성되면 데이터셋을 만든다. Studies 환경은 `uv sync`로 준비한다.

```bash
bash runs/sample/run3_mc_dataset.sh
```

기존 Phase2와 같은 150,000 / 49,000 / 50,000 이벤트로 train/val/test를 나눈다.
파일 단위로 seed 42로 섞으며 split 간 파일은 겹치지 않는다.
결과는 `output/dataset/sim-run3-singlemu-v001/`의
`train.root`, `val.root`, `test.root`와 각각의 `.h5`이다. 입력 목록은 `filelists/`에 남긴다.

Run3 Data는 ntuple만 제출한다. `--test`는 한 작업만 시험한다.

```bash
bash runs/sample/run3_data.sh --test
bash runs/sample/run3_data.sh
```

Run3 Data 데이터셋도 MC와 같은 train 150,000 / val 49,000 / test 50,000
이벤트로 맞춘다. 원본 chunk에 담긴 250,000개 이벤트 중 데이터셋에는 249,000개를 사용한다.
`output/dataset/data-run3-muon0-2024cde-v001/filelists/*.tsv`는 입력 파일별
`entry_start` 이상, `entry_stop` 미만의 이벤트 범위를 기록한다.

Phase2 MC는 DIGI-RAW 파일 목록을 한 번 지정하고, ReReco가 모두 끝난 뒤
ntuple을 제출한다.

gate의 SingleMu D110 PU200 원본 249개(12.81 TB)는 다음 명령으로 받는다.

```bash
bash runs/sample/fetch_phase2.sh
zellij attach fetch-phase2
```

16개 `rsync`가 백그라운드에서 실행된다. 같은 명령으로 중단된 전송을 재개한다.
저장 위치는 `output/sample/Phase2/MC/singlemu-d110-pu200/raw/`이며,
원격 파일 목록은 `manifest.tsv`, 진행·완료 상태는 `logs/`에 기록된다.
`logs/exitcode`가 `0`이면 전체 전송이 성공한 것이다.
SSH 터널을 사용할 때는 `DMR_REMOTE=joshin@127.0.0.1 DMR_SSH_PORT=22022`
환경 변수를 실행 명령 앞에 붙인다. 터널을 제공하는 PC는 전송 중 계속 연결되어 있어야 한다.

```bash
bash runs/sample/phase2_mc.sh rereco /path/to/digiraw-files.txt
bash runs/sample/phase2_mc.sh ntuple
```

새 결과와 로그는 `~/workspace/.store/deepmuonreco/chunk/` 아래에 저장된다.
테스트 제출 방법과 단계별 입력 조건은 `DeepMuonRecoSample/Run3/slurm/README.md`와
`DeepMuonRecoSample/Phase2/slurm/README.md`에 있다.
