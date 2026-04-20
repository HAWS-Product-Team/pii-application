import { Link, useLocation } from 'react-router-dom';

export default function Navbar() {
    const { pathname } = useLocation();

    const links = [
        { to: '/', label: 'Home'},
        { to: '/upload', label: 'Upload'},
        { to: '/dashboard', label: 'Dashboard' },
        { to: '/insights', label: 'Insights' },
    ];

    return (
        <nav className="bg-[#33B4A8] w-screen px-6 py-3">
            <div className="flex items-center justify-center">
                <div className="flex items-center space-x-6">
                    {links.map(({ to, label }) => {
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
                </div>
            </div>
        </nav>
    );
}