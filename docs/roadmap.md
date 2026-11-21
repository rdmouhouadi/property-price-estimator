# Roadmap

## V1: ML (done, 21 Nov 2026)

Data prep for 4.2M sales and 15.7M DPEs, the DVF × DPE join, leak-free features, five models compared, LightGBM chosen, tested once on 2025 (median error 16.0%).

## Part 2: MLOps (next, 22 Nov 2026)

- [ ] Convert `print` to the logger in `data/` scripts
- [ ] DVC pipeline (`dvc.yaml` stages, parameters in `params.yaml`), DVC remote for prepared Parquet
- [ ] MLflow tracking and model registry (champion alias)
- [ ] Tests (pytest for features and matching, pandera schema checks), ruff
- [ ] GitHub Actions: lint, tests, pipeline on a data sample
- [ ] Harmonise step (DPE labels under the current coefficient, from `params.yaml`)
- [ ] Weekly drift job (Evidently) → retrain trigger → challenger vs champion → promote
- [ ] Demo: recompute a sample at coefficient 1.7, show drift → retrain
- [ ] FastAPI `/predict` and Streamlit app (estimate + range + "what is my DPE worth?"), `noindex`
- [ ] Model and card on Hugging Face Hub, small `pip` package
- [ ] Docker images (pipeline, API, app); Terraform for AWS, validated with AWS Emulator
- [ ] Write-up part 2

## V1.1: model improvements

- [ ] Relax match uniqueness: keep a clearly best candidate (closest surface, then date)
- [ ] Ablation: DPE strictly before the sale vs the +30-day tolerance
- [ ] Prediction ranges: LightGBM quantile objective, with coverage measured (conformal calibration)
- [ ] Tuning: more trees or a higher learning rate (early stopping hit 2,646 of 3,000), Optuna search
- [ ] Walk-forward validation as a robustness check
- [ ] Benchmark pandas vs Polars (RAM, time) for ADR-0001
- [ ] Update LightGBM `eval_set` → `eval_X` / `eval_y`

## V1.5: app features

- [ ] 3D view beside the price monitor: pydeck/deck.gl, DPE coordinates (`ban_x/ban_y`, Lambert-93 → WGS-84), buildings via the RNB ID
- [ ] "Why this price": native TreeSHAP contributions as a waterfall

## V2: scale and scope

- [ ] Cloud cluster when data justifies it ([ADR-0002](adr/0002-scale-out-trigger.md)): DVF+ since 2014, pre-2021 DPE, BDNB; minikube Spark first, then EMR Serverless
- [ ] Energy-audit base: renovation cost vs value gain ("is renovating worth it?")
