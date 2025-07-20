# 🌐 Network Access Setup

## Quick Start

```bash
./start_network.sh
```

Then access from any device on your network:
- **Frontend**: `http://sentinelzero.prox:5173`
- **Backend API**: `http://sentinelzero.prox:5000`

## 🔧 What's Configured

### **Automatic Detection**
- API automatically detects localhost vs network access
- Dynamic URL routing based on access method
- Console logging shows which API URL is being used

### **Network Binding**
- **Flask Backend**: Binds to `0.0.0.0:5000`
- **React Frontend**: Binds to `0.0.0.0:5173`
- **CORS**: Allows all origins (`*`)
- **Vite Proxy**: No hostname restrictions

### **Mobile Access**
- Works with VPN setups
- Uses network DNS resolution
- Leverages existing port forwarding

## 🚨 Troubleshooting

### **API Calls Failing**
1. Check browser console for API URL
2. Verify domain: `ping sentinelzero.prox`
3. Test port: `telnet sentinelzero.prox 5000`

### **Frontend Loads, Backend Doesn't**
1. Check Flask process: `ps aux | grep python3`
2. Verify binding: `netstat -tlnp | grep 5000`
3. Check firewall settings

### **Debug Mode**
- Open browser dev tools
- Check Network tab for failed calls
- Look at Console for API URL being used 