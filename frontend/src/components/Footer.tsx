import {Link, useLocation} from 'react-router-dom'

export default function Footer() {
  const { pathname } = useLocation()
  const links = [
    { to: '/About', label: 'About'},
    { to: '/Privacy', label: 'Privacy'},
    { to: '/Terms', label: 'Terms'},
    { to: '/Contact', label: 'Contact'}
  ]

  
  return (
    <footer className='bg-[#6BADA0] w-screen sticky bottom-0'>
      <div className="max-w-4xl mx-auto px-6 py-6">
        <nav className="flex justify-center gap-8 mb-3 border-b py-2">
          {links.map(({to, label}) => {
            const isActive = pathname === to;
                        return (
                            <Link
                                key={to}
                                to={to}
                                className={`text-sm font-mono transition-colors ${
                                    isActive
                                        ? 'text-white border-b-2 border-white pb-0.5'
                                        : 'text-white/70 hover:text-white'
                                }`}
                            >
                                {label}
                            </Link>
                        );
          })}
        </nav>
        <p className="text-center text-white text-sm font-mono">
          © 2026 Personal Inflation Index Tracker. Track What Matters.
        </p>
      </div>
    </footer>
  );
}