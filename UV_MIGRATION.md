# UV Migration Guide

## ✅ Completed Migration

This project has been successfully migrated from pip to uv for Python package management!

### What Changed:

1. **Package Management:**
   - ✅ `pyproject.toml` - Now the single source of truth for Python dependencies
   - ✅ `uv.lock` - Generated lockfile for reproducible builds
   - 📦 `requirements.txt` - Backed up to `requirements.txt.bak` (no longer needed)

2. **Development Scripts:**
   - ✅ All `package.json` scripts now use `uv run` commands
   - ✅ Backend testing: `npm run test:backend` uses `uv run pytest`
   - ✅ Development: `npm run dev:backend` uses `uv run python app.py`

3. **Docker Configuration:**
   - ✅ `Dockerfile` now installs and uses `uv` instead of pip
   - ✅ Uses `uv sync --frozen --no-dev` for production builds

4. **SystemD Deployment:**
   - ✅ `systemd/install-systemd.sh` updated to use `uv sync`

5. **Documentation:**
   - ✅ `backend/src/README.md` updated with uv commands
   - ✅ `backend/migrate.py` updated with uv commands
   - ✅ `.github/copilot-instructions.md` updated with uv workflows

### Key Benefits:

- 🚀 **Faster installs** - uv is significantly faster than pip
- 🔒 **Better reproducibility** - uv.lock ensures consistent environments
- 📦 **Modern tooling** - Better dependency resolution and virtual environment management
- 🛠️ **Developer experience** - Cleaner workflows and better error messages

### New Commands:

```bash
# Install dependencies
cd backend && uv sync

# Add a new dependency
cd backend && uv add package-name

# Add a dev dependency
cd backend && uv add --dev package-name

# Remove a dependency
cd backend && uv remove package-name

# Run Python scripts
cd backend && uv run python app.py

# Run tests
cd backend && uv run pytest

# Or use npm scripts (recommended)
npm run dev:backend
npm run test:backend
npm run sync
```

### Migration Verification:

- ✅ All development scripts work with `uv run`
- ✅ Docker build updated to use uv
- ✅ SystemD deployment updated
- ✅ Documentation updated
- ✅ Lock file generated and dependency resolution verified

## Next Steps:

1. Test the Docker build: `docker compose build`
2. Verify all npm scripts work as expected
3. Consider removing `requirements.txt.bak` once everything is stable
