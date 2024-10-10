@net session >nul 2>&1
@if %errorLevel% neq 0 (
	@echo ERROR: Administrator mode required
	@pause
	@exit 1
)
netcfg.exe -u gigepdrv
@if %errorLevel% neq 0 (
	@pause
)