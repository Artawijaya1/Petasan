export function Intro({ backendUrl }) {
  return (
    <section className="intro">
      <div>
        <p className="eyebrow">PROJECT ENVIRONMENT ORCHESTRATION</p>
        <h1>Prepare your project.<br /><span>Monitor every step.</span></h1>
      </div>
      <p className="intro-note">Gateway <code>{backendUrl}</code></p>
    </section>
  )
}
