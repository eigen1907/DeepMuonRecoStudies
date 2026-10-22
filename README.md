# DeepMuonRecoStudies

`DeepMuonReco`의 모델 코드를 사용해 학습·변환·분석을 실행한다.
샘플 생산은 `DeepMuonRecoSample`, 실행 레시피는 이 저장소의 `runs/`에 둔다.
`DeepMuonReco`는 H5 chunk 읽기를 지원하는 `joshin/phase2-workflow` 브랜치를 사용한다.
H5 변환·chunk 추론·ONNX 변환·검증·플롯 코드는 이 저장소의 `scripts/`에 둔다.

결과는 `output/` 아래에 저장한다.

| 경로 | 내용 |
| --- | --- |
| `output/sample/<tag>/` | 원본·생산 chunk와 생산 로그 |
| `output/dataset/<tag>/` | train/val/test H5와 입력 목록 |
| `output/model/<exp>/<run>/` | 학습 설정·체크포인트·평가·로그 |
| `output/predictions/<exp>/<run>/` | 플롯용 validation/test 점수 |
| `output/onnx/<exp>/<run>/` | ONNX 모델 파일 |
| `output/benchmark/` | CMSSW 실행 로그·FastTimerService 결과·검증 EDM |
| `output/plots/` | PNG 그림 |

대용량 원본·생산 chunk는 `~/workspace/.store/deepmuonreco/`에 둔다.
`output/sample`, `output/dataset`은 기존 저장소를 가리키는 심볼릭 링크다.
현재 기준 모델은 `output/model/phase2-d110/baseline-01`이다.
기존 `DeepMuonReco/logs` 경로는 `output/model`을 가리키는 호환 링크다.

## 플롯

```bash
uv sync
bash runs/plot/plot_phase2_dataset.sh
bash runs/plot/plot_run3_dataset.sh
bash runs/plot/plot_phase2_models.sh
```

입력과 모델은 `--h5`, `--model`로 지정한다. 모델은 run 디렉터리나 체크포인트다.
`val.h5`는 입력 `test.h5` 옆에서 찾으며 필요한 점수는 자동 추론한다.
전체 H5를 chunk로 읽고 PNG마다 Axes 하나를 사용한다.
효율·거부율 오차막대는 68.3% Clopper–Pearson 구간이다.
`eff_threshold.png`는 score threshold에 따른 TrackerMuon 효율과 background 거부율을 표시한다.

## 학습

```bash
bash runs/train/train_sanity.sh   # GPU 0, 2 epoch
bash runs/train/train_default.sh  # GPU 0~3, 기본 설정
bash runs/train/train_100ep.sh    # GPU 0~3, 100 epoch
```

분리된 zellij 세션에서 실행하며 접속 명령을 출력한다. 각 작업의 시드는 무작위다.
학습과 Aim 데이터는 `output/model/`에 저장한다.

```bash
../DeepMuonReco/.venv/bin/aim up --repo output/model --port 43800
```

## ONNX와 CMSSW

저장된 모델은 `data/model.onnx`다. 같은 원본 RAW에서 표준 Phase-2 RECO를 실행하며 다섯 경우를 비교한다.

```bash
# 기본값: 100 events, probability threshold 0.38735
raw_input=/eos/user/j/joshin/deepmuonreco/phase2/reco/41ea10ad-0471-4681-8bb1-140d3759674a.root
bash runs/benchmark/run.sh all "$raw_input"
```

| 모드 | ONNX backend | preselection |
| --- | --- | --- |
| `baseline` | 없음 | 없음 |
| `cpu_nonfilter` | CPU | 끔 |
| `cpu_filter` | CPU | 켬 |
| `gpu_nonfilter` | CUDA | 끔 |
| `gpu_filter` | CUDA | 켬 |

`baseline`은 `../cmssw/base/CMSSW_14_0_9`, 나머지는 `../cmssw/onnx/CMSSW_14_0_9`를 사용한다.
표준 재구성은 모든 경우 CPU에서 실행하며 `MuonIdONNXProducer`의 backend만 바꾼다.
`all` 대신 모드 하나를 지정할 수 있다. 세 번째 인자는 이벤트 수, 네 번째는 threshold다.
기본값 0.38735는 모델 평가에서 signal efficiency 99.898%, background rejection 52.25%인 지점이다.

실행 진입점은 `runs/benchmark/run.sh`, CMSSW 설정은 `runs/benchmark/run_cfg.py`다.
RAW2DIGI와 표준 RECO가 offline track·segment를 만들므로 별도 입력 준비 단계가 없다.
기존 축소 입력 `output/benchmark/input/reco_1000.root`는 부분 테스트용이며 이 전체 RECO 입력으로 사용하지 않는다.

시간은 공식 FastTimerService의 module real time으로 측정한다.
`muons1stStep`은 기존 `MuonIdProducer`, `muonIdONNX`는 입력 구성·추론 모듈이다.
순수한 시간 절감은 두 모듈의 합과 baseline을 비교한다. TrackerMuon 생성은 `muons1stStep` 내부 작업이다.
4 threads / 1 stream에서 공식 FwkReport의 이벤트 식별자와 이벤트별 FastTimer 결과를 연결한다.
표준 RECO의 calorimeter·isolation·global-muon 설정을 유지하며, 기본 시간 측정에는 ROOT 출력을 쓰지 않는다.
공식 `AsciiOutputModule`을 `verbosity=0`으로 사용해 표준 RECO 출력과 같은 제품을 요청한다.
따라서 ROOT 파일을 쓰지 않아도 재구성 task가 실제 실행된다.

실행 로그·설정·`resources.json`은 `output/benchmark/{모드}/`에 저장한다.
이 workspace의 `output/benchmark`는 EOS의 원자료 디렉터리를 가리킨다.
결과는 `output/plots/benchmark/baseline-01/` 아래 PNG로 만든다.

- `paired_timing.png`: x축 baseline 시간, y축 (filtered Muon ID + ONNX) / baseline 비율. CPU와 GPU filter만 표시한다.
- `timing_distribution.png`: CPU/GPU 패널에 baseline `MuonIdProducer`와 filtered `MuonIdProducer + ONNX`의 이벤트별 합산 시간을 비교한다. 범례에는 평균 시간을 MuonIdProducer + ONNX 성분으로 나눠 표시한다.
- `timing_sunburst.png`: GPU filter 실행의 전체 모듈 시간을 subsystem → module로 보여준다.

Sunburst 분류는 `data/benchmark_groups.json`의 [공식 circles Phase-II 매핑](https://github.com/cms-sw/circles/blob/6f3bf575e169f4cce145638922e8d67b4ad9de1f/web/groups/reco_PhaseII.json)을 사용한다.
병렬 실행 중인 모듈 시간도 합산하므로, sunburst의 합계와 전체 작업의 경과 시간은 구분한다.

CMSSW 환경에서 `python3 scripts/plot_benchmark.py`로 plot만 다시 만들 수 있다.
이 그림에는 `baseline`, `cpu_filter`, `gpu_filter` 결과를 사용한다.
표시하는 signal efficiency 99.9%는 모델 평가에서 정한 working point이며, 현재 재구성 샘플에서 새로 측정한 효율이 아니다.

물리 결과 검증은 같은 `run_cfg.py`의 `validationOutput=/path/to/muons.root`로 EDM을 저장한 뒤
`scripts/validate_benchmark.py`로 baseline/nonfilter muon 일치, CPU/CUDA 점수·threshold 판정과 muon 보존율을 확인한다.
검증 EDM 출력은 시간 측정과 별도 실행에서 사용한다.
기본 조건은 샘플 생산 설정의 Phase2C17I13M9 / D110 / `140X_mcRun4_realistic_v4`다.
