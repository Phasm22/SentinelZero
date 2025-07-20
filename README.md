# SentinelZero

A comprehensive network scanning and monitoring application with React frontend and Flask backend.

## 📁 Project Structure

```
sentinelZero/
├── backend/                 # Flask API and backend logic
│   ├── app.py              # Main Flask application
│   ├── requirements.txt    # Python dependencies
│   ├── sentinelzero.db    # SQLite database
│   ├── scans/             # Scan results and XML files
│   ├── templates/         # Flask templates
│   ├── tests/            # Backend tests
│   └── ...
├── frontend/              # React application
│   ├── react-sentinelzero/ # React app directory
│   ├── package.json       # Node.js dependencies
│   ├── vite.config.js     # Vite configuration
│   └── ...
└── docs/                  # Documentation
    ├── README.md          # Main documentation
    ├── NETWORK_SETUP.md   # Network configuration
    ├── QUICK_START.md     # Quick start guide
    └── ...
```

## 🚀 Quick Start

### Backend (Flask API)
```bash
cd backend
python3 app.py
```

### Frontend (React App)
```bash
cd frontend/react-sentinelzero
npm run dev
```

## 🔧 Development

- **Backend**: Flask API with SQLite database
- **Frontend**: React with Vite build system
- **Network Access**: Configured for `sentinelzero.prox` domain
- **Ports**: Backend (5000), Frontend (5173)

## 📚 Documentation

See the `docs/` directory for detailed documentation.

---

*This structure is organized to prevent confusion and ensure proper separation of concerns.* 