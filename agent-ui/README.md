# 💼 Job Agent UI (Standalone React 18 + Vite Dashboard)

This is the independent, decoupled User Interface for the Multi-Agent Job Search & Apply System.

## 🚀 Running the UI Independently

### 1. Install dependencies (already completed):
```bash
npm install
```

### 2. Start the Development Server:
```bash
npm run dev
```
The UI will start on **`http://localhost:3000`**.

### 3. Backend Proxy Configuration:
By default, the Vite dev server proxies all `/api/*` calls directly to the Manager Agent at:
```
http://localhost:8000
```
If your backend is running on a different port or host, create a `.env` file:
```ini
VITE_BACKEND_URL=http://localhost:8000
```

## 🏗️ Production Build
```bash
npm run build
npm run preview
```

## 🐳 Docker (Optional Standalone Container)
```bash
docker build -t job-agent-ui .
docker run -p 3000:80 job-agent-ui
```
