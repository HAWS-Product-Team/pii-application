import { BrowserRouter as Router, Route, Routes} from 'react-router-dom'
import HomePage from './pages/HomePage'
import DashboardPage from './pages/DashboardPage'
import CalculatePage from './pages/CalculatePage'
import './App.css'
import Navbar from './components/Navbar'
import Footer from './components/Footer'

function App() {

  return (
    <Router>
      <div className='min-h-screen flex flex-col'>
        <div className='flex-1'>
          <Navbar/>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/calculate" element={<CalculatePage />} />
        </Routes>
        </div>
        <Footer/>
      </div>
    </Router>
  )
}

export default App
