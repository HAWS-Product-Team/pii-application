import { Link } from 'react-router-dom'

export default function Homepage() {

    return (
        <div className="w-screen mx-auto py-10 text-center">
            <h1 className="text-4xl">
                Track Your Inflation,<br/> Not Theirs
            </h1>
            <p className="max-w-2xl mx-auto py-10">
                Official inflation rates don't reflect your life. Build a personal
                inflation index based on what you actually buy, and see how prices 
                really affect you. <Link to={"/"} className='text-[#33B4A8]'> Learn more </Link>
            </p>
            <Link to={"/calculate"} className='bg-[#33B4A8] rounded-full text-white px-10 py-1'>
                Calculate
            </Link>
        </div>
    )
}