# DeepMuonRecoStudies

`docs/` 슬라이드의 그림을 H5와 Python으로 그린다.

```bash
uv sync
bash runs/plot_phase2_dataset.sh
bash runs/plot_run3_dataset.sh
bash runs/plot_phase2_models.sh
```

다른 입력과 모델은 bash 파일의 `--h5`, `--model` 경로를 바꾼다.

모델 경로에는 run 디렉터리나 체크포인트 파일을 넣는다. `val.h5`는 입력
`test.h5`와 같은 디렉터리에서 찾는다. 필요한 점수는 자동 추론하며,
검증셋에서 95.0%, 99.0%, 99.9% 기준을 계산한다. 결과는 `plots/dataset/`과
`plots/<model-run>/`에 저장된다. 입력 H5가 바뀌면 해당 run의 `predictions/`
점수 파일을 갱신한다.

기본 H5는 Phase 2 전체 테스트셋이다. 데이터셋·추론·모델 플롯은 각각
128·256·64개 이벤트씩 읽는다. `track_is_good_track`에는 `pT > 0.5`,
`p > 2.5`, `|eta| < 3`이 이미 포함돼 있다. 각 PNG에는 Axes가 하나만 있다.
효율·거부율 오차막대는 68.3% Clopper–Pearson, 분포 히스토그램 오차막대는
Poisson(Garwood) 구간이다.

Run 3 H5를 지정하면 슬라이드의 시뮬레이션과 다른 Muon0 실데이터를 그린다.

## 학습

`bash runs/train_sanity.sh`는 2 epoch 점검을 실행한다.
`bash runs/train_default.sh`는 기본 설정으로 GPU 0~3에 4개 작업을 실행한다.
`bash runs/train_100ep.sh`는 같은 방식으로 100 epoch씩 실행한다.

각 스크립트는 분리된 zellij 세션을 만들고 접속 명령을 출력한다. 기본 데이터
경로가 이 서버와 달라 데이터 디렉터리를 지정한다. GPU는
`CUDA_VISIBLE_DEVICES`로 나누므로 각 작업에서는 `cuda:0`으로 보인다.
시드는 작업마다 무작위로 정해지며 결과는 `../DeepMuonReco/logs/`에 저장된다.
