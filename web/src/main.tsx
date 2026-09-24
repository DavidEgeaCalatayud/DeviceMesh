import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './app/App'
import './app/styles.css'
import './app/device-detail.css'
import './app/operator-console.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
