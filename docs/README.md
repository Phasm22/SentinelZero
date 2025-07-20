# SentinelZero v1.0

A professional network security scanner and dashboard for cybersecurity homelabs and penetration testing environments.

## 🚀 Features

### **Core Functionality**
- **Network Scanning**: Comprehensive nmap-based scanning with multiple scan types
- **Real-time Monitoring**: Live scan progress and log streaming via WebSocket
- **Smart Host Detection**: Automatic discovery of network devices with MAC/vendor info
- **Port Analysis**: Detailed port state analysis (open, filtered, closed)
- **Vulnerability Detection**: Built-in vulnerability scanning with script execution

### **User Interface**
- **Modern React Frontend**: Professional UI with dark mode support
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Real-time Updates**: Live progress bars and log streaming
- **Scan History**: Complete scan history with diff comparisons
- **Settings Management**: Network configuration and alert settings

### **Advanced Features**
- **Scheduled Scans**: Automated scanning with configurable schedules
- **Push Notifications**: Integration with Pushover for alerts
- **Export Capabilities**: XML export and detailed reporting
- **Network Discovery**: Automatic network interface detection
- **Multi-host Support**: Scales to large networks (1000+ hosts)

## 🛠 Tech Stack

- **Backend**: Flask, SQLite, Flask-SocketIO
- **Frontend**: React 18, Vite, Tailwind CSS
- **Scanning**: Nmap with custom port profiles
- **Testing**: Playwright, Pytest
- **Deployment**: Docker support

## 📦 Quick Start

### **Option 1: Development Setup**
```bash
# Clone and setup
git clone <repo>
cd sentinelzero

# Install dependencies
pip install -r requirements.txt
npm install

# Start the application
npm run dev:all
```

### **Option 2: Docker Deployment**
```bash
# Build and run
docker build -t sentinelzero .
docker run -p 5000:5000 -p 5173:5173 sentinelzero
```

### **Option 3: Network Access**
```bash
# For network-wide access
./start_network.sh
```

## 🌐 Access Points

- **React Frontend**: http://localhost:5173
- **Flask Backend**: http://localhost:5000
- **Network Access**: http://sentinelzero.prox:5173 (if configured)

## 📋 Scan Types

- **Quick Scan**: Fast port scan of common services
- **Full TCP**: Comprehensive TCP port scan
- **Vulnerability Scan**: Script-based vulnerability detection
- **IoT Scan**: Specialized IoT device scanning
- **Custom Scans**: User-defined scan configurations

## 🔧 Configuration

### **Network Settings**
- Automatic network interface detection
- Configurable target networks
- Custom port profiles
- Scan timing optimization

### **Alert Settings**
- Pushover integration for notifications
- Configurable alert levels
- Scan completion notifications
- Error reporting

## 🧪 Testing

```bash
# Run all tests
npm run test

# Run backend tests
pytest

# Run frontend tests
npm run test:frontend
```

## 📚 Documentation

- [Quick Start Guide](QUICK_START.md) - Development setup
- [Network Setup](NETWORK_SETUP.md) - Network access configuration
- [Migration Plan](MIGRATION_PLAN.md) - Architecture evolution

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

---

**Built with ❤️ for the cybersecurity community** 