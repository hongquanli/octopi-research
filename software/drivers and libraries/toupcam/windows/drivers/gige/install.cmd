@net session >nul 2>&1
@if %errorLevel% neq 0 (
	@echo ERROR: Administrator mode required
	@pause
	@exit 1
)
cd /d "%~p0"
netcfg.exe -v -l gigepdrv.inf -c s -i gigepdrv
@if %errorLevel% neq 0 (
	@pause
)