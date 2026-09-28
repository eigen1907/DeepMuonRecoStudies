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

`gensim` 249개와 `minbias` 2490개를 제출한다. 현재 실행 중인 옛 배열은
예전 출력 경로를 사용하므로, 그 결과로 후속 단계를 실행하려면
`run3_mc.sh` 맨 위의 `signal`, `minbias` 경로를 바꾼다.

Run3 Data는 ntuple만 제출한다. `--test`는 한 작업만 시험한다.

```bash
bash runs/sample/run3_data.sh --test
bash runs/sample/run3_data.sh
```

Phase2 MC는 DIGI-RAW 파일 목록을 한 번 지정하고, ReReco가 모두 끝난 뒤
ntuple을 제출한다.

```bash
bash runs/sample/phase2_mc.sh rereco /path/to/digiraw-files.txt
bash runs/sample/phase2_mc.sh ntuple
```

새 결과와 로그는 `~/workspace/.store/deepmuonreco/chunk/` 아래에 저장된다.
테스트 제출 방법과 단계별 입력 조건은 `DeepMuonRecoSample/Run3/slurm/README.md`와
`DeepMuonRecoSample/Phase2/slurm/README.md`에 있다.
