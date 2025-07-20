# Quick Start Guide

## 🚀 Development Setup

### **Prerequisites**
- Python 3.8+
- Node.js 16+
- Nmap installed

### **Installation**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### **Running the Application**

#### **Option 1: Full Stack (Recommended)**
```bash
npm run dev:all
```
- React frontend: http://localhost:5173
- Flask backend: http://localhost:5000

#### **Option 2: Frontend Only**
```bash
npm run dev
```
- React dev server: http://localhost:5173

#### **Option 3: Backend Only**
```bash
npm run dev:backend
```
- Flask server: http://localhost:5000

## 🔧 Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start React frontend only |
| `npm run dev:backend` | Start Flask backend only |
| `npm run dev:all` | Start both frontend and backend |
| `npm run build:frontend` | Build React for production |
| `npm run test` | Run all tests |
| `npm run test:frontend` | Run React tests |
| `npm run test:backend` | Run Flask tests |

## 🌐 Network Access

For network-wide access (mobile, other devices):

```bash
./start_network.sh
```

Then access via: `http://sentinelzero.prox:5173`

## 📝 Notes

- React frontend proxies API calls to Flask backend
- Socket.IO connections are automatically handled
- Both UIs can run simultaneously
- Hot reload enabled for development 