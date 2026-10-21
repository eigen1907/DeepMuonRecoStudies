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
| `output/plots/` | 그림·ONNX/CMSSW 검증 입력·결과·로그 |

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

```bash
bash runs/onnx/baseline.sh       # model.onnx 저장
bash runs/plot/validate_onnx.sh  # PyTorch와 ONNX 비교·CMSSW 검증 입력 생성
bash runs/cmssw/baseline.sh      # CMSSW 빌드와 추론 비교
bash runs/cmssw/phase2_reco.sh file:/path/to/phase2-d110-digiraw.root
```

`output/onnx/`에는 ONNX 파일만 저장한다.
검증 입력·결과·로그는 `output/plots/{onnx,cmssw}/`에 저장한다.
Phase2 ReReco 예제는 기본적으로 점수만 계산하며, 컷은 설정 파일에서 켠다.
CMSSW core는 `../CMSSW/CMSSW_14_0_9/src`의 `joshin/deepmuon-phase2` 브랜치다.
예제 설명은 [DeepMuonRecoSample/Inference](../DeepMuonRecoSample/Inference/README.md),
샘플 생산 순서는 [runs/sample/README.md](runs/sample/README.md)에 있다.
