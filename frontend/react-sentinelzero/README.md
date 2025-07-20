# SentinelZero React Frontend

Modern React frontend for SentinelZero, replacing the Bootstrap-based Flask templates.

## Features

- ⚡ **Vite** - Fast development and build
- 🎨 **Tailwind CSS** - Modern utility-first CSS framework
- 🔄 **Socket.IO** - Real-time updates from Flask backend
- 🌙 **Dark Mode** - Built-in theme switching
- 📱 **Responsive** - Mobile-first design
- 🧭 **React Router** - Client-side routing

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Axios** - HTTP client
- **Socket.IO Client** - Real-time communication

## Development

### Prerequisites

- Node.js 18+
- Flask backend running on port 5000

### Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Open http://localhost:5173

### Build

```bash
npm run build
```

## Migration Status

### ✅ Completed
- [x] Project structure setup
- [x] Tailwind CSS configuration
- [x] React Router setup
- [x] Socket.IO integration
- [x] Toast notification system
- [x] Layout component with sidebar
- [x] Dashboard page (basic)
- [x] API service layer
- [x] Dark mode support

### 🚧 In Progress
- [ ] Complete Dashboard functionality
- [ ] Scan History page
- [ ] Settings page
- [ ] Scan Types management
- [ ] Modal components
- [ ] Form components

### 📋 Next Steps
1. **Complete API Integration** - Connect all Flask endpoints
2. **Add Missing Pages** - Implement full functionality for all pages
3. **Component Library** - Create reusable UI components
4. **Testing** - Add unit and integration tests
5. **Production Build** - Optimize for deployment

## Architecture

```
src/
├── components/     # Reusable UI components
├── contexts/      # React contexts (Socket, Toast)
├── hooks/         # Custom React hooks
├── pages/         # Page components
├── utils/         # Utility functions (API, helpers)
└── App.jsx        # Main app component
```

## API Integration

The React app communicates with the Flask backend via:
- **REST API** - HTTP requests for CRUD operations
- **Socket.IO** - Real-time scan updates and logs

## Styling

Uses Tailwind CSS with custom components that match the original Bootstrap design:
- `.btn` - Button styles
- `.card` - Card containers
- `.table` - Table styles
- `.badge` - Status badges
- `.modal` - Modal dialogs

## Development Notes

- Proxy configuration routes `/api` and `/socket.io` to Flask backend
- Dark mode toggles CSS classes on document element
- Toast notifications replace Bootstrap alerts
- Responsive sidebar with mobile overlay 