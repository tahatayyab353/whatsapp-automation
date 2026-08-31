export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-slate-50 text-slate-900">
      <div className="max-w-xl w-full bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full mb-4 border border-emerald-200">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          CHUNK 0 Foundation Active
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 mb-2">
          AI Receptionist Platform
        </h1>
        <p className="text-slate-600 text-sm mb-6">
          WhatsApp AI Automation for Dental & Aesthetic Clinics in Karachi, Pakistan.
        </p>
        <div className="p-4 bg-slate-50 rounded-lg text-left text-xs text-slate-500 font-mono space-y-1 border border-slate-100">
          <p><strong className="text-slate-700">Frontend:</strong> Next.js App Router (TypeScript + Tailwind CSS)</p>
          <p><strong className="text-slate-700">Backend:</strong> FastAPI + SQLAlchemy (PostgreSQL)</p>
          <p><strong className="text-slate-700">Status:</strong> Scaffolding & System Health Check Ready</p>
        </div>
      </div>
    </main>
  );
}
