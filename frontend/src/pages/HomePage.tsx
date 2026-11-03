import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ComparisonCard from '../components/ComparisonCard'
import HighestInflationCard from '../components/HighestInflationCard'
import { getWelcomeMessage } from '../api'

export default function Homepage() {
    const [welcomeMessage, setWelcomeMessage] = useState('')
    const [apiError, setApiError] = useState('')

    useEffect(() => {
        getWelcomeMessage()
            .then(setWelcomeMessage)
            .catch((error: unknown) => {
                console.error('Failed to load welcome message:', error)
                setApiError('Welcome message could not be loaded.')
            })
    }, [])

    return (
        <div className="w-screen mx-auto py-10 text-center">
            <h1 className="text-4xl">
                Track Your Inflation,<br /> Not Theirs
            </h1>

            <div className="max-w-2xl mx-auto px-4">
                {welcomeMessage && (
                    <p className="py-3" role="status">
                        {welcomeMessage}
                    </p>
                )}

                {apiError && (
                    <p className="py-3 text-red-600" role="alert">
                        {apiError}
                    </p>
                )}
            </div>

            <Link
                to={"/upload"}
                className="bg-[#33B4A8] rounded-full text-white px-10 py-1"
            >
                Calculate
            </Link>

            <div className="px-4">
                <div className="flex justify-center space-x-5 py-5 my-5 px-5 border-[#33B4A8] border-2 rounded-lg max-w-2xl mx-auto">
                    <ComparisonCard />
                    <HighestInflationCard />
                </div>
            </div>
        </div>
    )
}
