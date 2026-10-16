param([string]$Results = 'results-new')
# Writes a fresh run to $Results and its tables/figures to $Results\report,
# leaving the archived results/ and report/ untouched.
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Semantic tests failed' }
    $env:NQUEENS_INTEGRATION = '1'
    python -m unittest tests.test_models.ModelTests.test_exact_backends -v
    if ($LASTEXITCODE -ne 0) { throw 'Solver integration tests failed' }
    python -m nqueens.benchmark --results $Results
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark failed' }
    python -m nqueens.analyze --results $Results --report "$Results\report"
    if ($LASTEXITCODE -ne 0) { throw 'Result audit failed' }
    python -m nqueens.report_details --results $Results --report "$Results\report"
    if ($LASTEXITCODE -ne 0) { throw 'Report detail checks failed' }
} finally {
    Pop-Location
}
