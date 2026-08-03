import Upload from "./pages/Upload";
import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";

function Placeholder({ title }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <h1 className="font-serif text-4xl font-black text-black/20">{title} — coming soon</h1>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-[#f4f1ea]">
      <Navbar />
      <main className="mx-auto max-w-7xl px-6 py-10">
        <Routes>
          <Route path="/" element={<Upload />} />
          <Route path="/gallery" element={<Placeholder title="Gallery" />} />
          <Route path="/search" element={<Placeholder title="Search" />} />
          <Route path="/profile" element={<Placeholder title="Profile" />} />
        </Routes>
      </main>
    </div>
  );
}