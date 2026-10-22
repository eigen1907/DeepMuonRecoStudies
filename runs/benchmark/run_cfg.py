"""Compare ONNX preselection during standard Phase-2 reconstruction from RAW."""

import math
from pathlib import Path

import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
from Configuration.Eras.Era_Phase2C17I13M9_cff import Phase2C17I13M9

options = VarParsing("analysis")
options.setDefault("maxEvents", 100)
for name, default, kind, description in (
    ("mode", "baseline", VarParsing.varType.string, "Benchmark case"),
    ("threshold", 0.38735, VarParsing.varType.float, "Probability cut"),
    ("modelPath", str(Path(__file__).resolve().parents[2] / "data/model.onnx"),
     VarParsing.varType.string, "ONNX model path"),
    ("validationOutput", "", VarParsing.varType.string, "Optional EDM validation file"),
):
    options.register(name, default, VarParsing.multiplicity.singleton, kind, description)
options.parseArguments()
if options.mode not in ("baseline", "cpu_nonfilter", "cpu_filter", "gpu_nonfilter", "gpu_filter"):
    raise ValueError("Unknown benchmark mode: " + options.mode)
if not math.isfinite(options.threshold) or not 0 <= options.threshold <= 1:
    raise ValueError("threshold must be a probability between 0 and 1")
if not options.inputFiles and options.maxEvents != 0:
    raise ValueError("Pass inputFiles=file:/path/to/original-raw.root")

# Same standard reconstruction, era, geometry, conditions and aging as the
# Phase2 sample recipe. RecoSim and ROOT output are unnecessary for timing.
process = cms.Process("MUONBENCH", Phase2C17I13M9)
for configuration in (
    "Configuration.StandardSequences.Services_cff",
    "FWCore.MessageService.MessageLogger_cfi",
    "Configuration.EventContent.EventContent_cff",
    "Configuration.Geometry.GeometryExtended2026D110Reco_cff",
    "Configuration.StandardSequences.MagneticField_cff",
    "Configuration.StandardSequences.RawToDigi_cff",
    "Configuration.StandardSequences.Reconstruction_cff",
    "Configuration.StandardSequences.FrontierConditions_GlobalTag_cff",
):
    process.load(configuration)
from Configuration.AlCa.GlobalTag import GlobalTag
from SLHCUpgradeSimulations.Configuration.aging import customise_aging_1000

process.GlobalTag = GlobalTag(process.GlobalTag, "140X_mcRun4_realistic_v4", "")
process = customise_aging_1000(process)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(options.maxEvents))
process.source = (
    cms.Source("PoolSource", fileNames=cms.untracked.vstring(options.inputFiles))
    if options.inputFiles else cms.Source("EmptySource")
)
process.options = cms.untracked.PSet(
    numberOfThreads=cms.untracked.uint32(4),
    numberOfStreams=cms.untracked.uint32(1),
    accelerators=cms.untracked.vstring("cpu"),
    wantSummary=cms.untracked.bool(False),
)
process.raw2digi_step = cms.Path(process.RawToDigi)
process.reconstruction_step = cms.Path(process.reconstruction)
if options.mode != "baseline":
    from RecoMuon.MuonIdentification.muonIdONNX_cff import customizeMuonIdONNX

    process = customizeMuonIdONNX(
        process, str(Path(options.modelPath).resolve()),
        backend="cuda" if options.mode.startswith("gpu_") else "cpu",
        applyFilter=options.mode.endswith("_filter"), threshold=options.threshold,
    )

# Task producers run only when their products are requested. Demand the same
# products as standard RECO output, with no serialization or ROOT file writing.
process.recoProducts = cms.OutputModule(
    "AsciiOutputModule", verbosity=cms.untracked.uint32(0),
    outputCommands=process.RECOEventContent.outputCommands,
)
process.consumeRECO = cms.EndPath(process.recoProducts, process.reconstructionTask)

process.MessageLogger.cerr.FwkReport.reportEvery = 1
process.MessageLogger.cerr.FwkReport.limit = cms.untracked.int32(-1)
process.MessageLogger.cerr.DeepMuonReco = cms.untracked.PSet(limit=cms.untracked.int32(-1))
process.MessageLogger.cerr.FastReport = cms.untracked.PSet(limit=cms.untracked.int32(-1))
process.load("HLTrigger.Timer.FastTimerService_cfi")
process.FastTimerService.printEventSummary = True
process.FastTimerService.printJobSummary = True
process.FastTimerService.writeJSONSummary = True
process.FastTimerService.jsonFileName = "resources.json"
process.FastTimerService.enableDQM = False

if options.validationOutput:
    process.validation = cms.OutputModule(
        "PoolOutputModule", fileName=cms.untracked.string(options.validationOutput),
        outputCommands=cms.untracked.vstring(
            "drop *", *(
                "keep *_" + label + "_*_MUONBENCH"
                for label in (
                    "muons1stStep", "muonIdONNX", "generalTracks", "offlineBeamSpot",
                    "dt4DSegments", "cscSegments", "rpcRecHits", "gemRecHits", "gemSegments",
                )
            ),
        ),
    )
    process.writeValidation = cms.EndPath(process.validation)
