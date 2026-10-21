@echo off
echo ==============================================================
echo Fixing Git: Removing 118MB price_cache.db from local commit
echo ==============================================================

REM 1. Undo the last unpushed commit (keeps all your code changes safe)
git reset --soft HEAD~1

REM 2. Unstage the large database file
git reset HEAD data/price_cache.db 2>nul
git rm --cached data/price_cache.db 2>nul

REM 3. Stage the rest of the code and commit
git add .
git commit -m "Update strategy and scanner code (exclude database cache)"

echo.
echo ==============================================================
echo SUCCESS! The 118MB database has been removed from the commit.
echo You can now go to GitHub Desktop and click 'Push origin'.
echo ==============================================================
pause
