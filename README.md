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

Run 3 H5를 지정하면 슬라이드의 시뮬레이션과 다른 Muon0 실데이터를 그린다.
