$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Semantic tests failed' }
    $env:NQUEENS_INTEGRATION = '1'
    python -m unittest tests.test_models.ModelTests.test_exact_backends -v
    if ($LASTEXITCODE -ne 0) { throw 'Solver integration tests failed' }
    python -m nqueens.benchmark
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark failed' }
    python -m nqueens.analyze
    if ($LASTEXITCODE -ne 0) { throw 'Result audit failed' }
} finally {
    Pop-Location
}
