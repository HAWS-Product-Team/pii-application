import Card from "./Card";



export default function ComparisonCard() {
    return (
    <Card className="p-4 mx-auto max-w-md w-96 bg-[#33B4A8] rounded-lg text-white">
        <h3 className="text-lg font-semibold">Your Personal Inflation Rate</h3>
        <p className="text-3xl border-b-2 pb-7 pt-3 border-white">+3.41%</p>
        <div className="flex justify-center py-3 space-x-8">
            <p>
                Your Inflation <br/>
                +3.41%
            </p>
            <p>
                Consumer Price Index <br/>
                +2.23%
            </p>
        </div>
    </Card>
    );
}