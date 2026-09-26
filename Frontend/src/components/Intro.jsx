export function Intro({ backendUrl }) {
  return (
    <section className="intro">
      <div>
        <p className="eyebrow">ORKESTRASI LINGKUNGAN PROYEK</p>
        <h1>Siapkan proyek.<br /><span>Pantau setiap langkah.</span></h1>
      </div>
      <p className="intro-note">Gateway <code>{backendUrl}</code></p>
    </section>
  )
}
