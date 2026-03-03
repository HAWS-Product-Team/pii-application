import { Link, useLocation } from 'react-router-dom';
import logo from '../assets/Logo.svg';

export default function Navbar() {
    const { pathname } = useLocation();

    const links = [
        { to: '/calculate', label: 'Calculate'},
        { to: '/dashboard', label: 'Dashboard' },
        { to: '/insights', label: 'Insights' },
    ];

    return (
        <nav className="bg-[#33B4A8] w-screen px-6 py-3">
            <div className="flex items-center justify-between">
                <Link to="/" className="flex items-center gap-2 w-[160px]">
                    <img src={logo} alt="logo" className="h-8 w-8" />
                </Link>
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
                <div className="w-[160px]" />
            </div>
        </nav>
    );
}