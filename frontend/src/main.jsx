import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider, createTheme } from '@mantine/core'
import { BrowserRouter } from 'react-router-dom'
import '@mantine/core/styles.css'
import App from './App.jsx'

const theme = createTheme({
  primaryColor: 'uc-blue',
  fontFamily: 'Lora, Georgia, serif',
  headings: { fontFamily: 'Lora, Georgia, serif' },
  colors: {
    'uc-blue': [
      '#e6f4fb', '#c2e3f6', '#8fcbee', '#5ab3e6', '#1295D8',
      '#0f85c2', '#0c74ab', '#096394', '#06527d', '#034166',
    ],
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="light">
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </MantineProvider>
  </StrictMode>,
)
