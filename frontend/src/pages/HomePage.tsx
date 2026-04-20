import { Link } from 'react-router-dom'
import ComparisonCard from '../components/ComparisonCard'
import HighestInflationCard from '../components/HighestInflationCard'
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
            <Link to={"/upload"} className='bg-[#33B4A8] rounded-full text-white px-10 py-1'>
                Calculate
            </Link>
            <div className=' px-4'>
                <div className='flex justify-center space-x-5 py-5 my-5 px-5 border-[#33B4A8] border-2 rounded-lg max-w-2xl mx-auto'>
                    <ComparisonCard/>
                    <HighestInflationCard/>
                </div>
            </div>
        </div>
    )
}