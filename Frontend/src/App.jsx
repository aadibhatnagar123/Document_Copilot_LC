import { Routes, Route } from "react-router-dom"
import UploadPage from "./pages/UploadPage"
import RunPage from "./pages/RunPage"

function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
       <Route path="/run/:runId" element={<RunPage />} />
    </Routes>
  )
}

export default App