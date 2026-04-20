import Card from "./Card";

export default function CategoryCard () {

    return (
        <Card className="p-4 mx-auto max-w-md w-96 bg-[#33B4A8] rounded-lg text-white">
            <h3 className="text-lg font-semibold">Inflation by category</h3>
            <p className="pb-7 pt-3">vs CPI baseline (+2.23%)</p>
            <div className="flex justify-center py-3 space-x-8">
                <ul>
                    <li>
                        <span className="whitespace-nowrap">Groceries</span>
                        <div className="bg-gray-200 rounded-full w-full h-2 dark:bg-neutral-700">
                            <div className="h-full rounded-full bg-green-600 dark:bg-green-500"></div>
                        </div>
                    </li>
                </ul>
            </div>
        </Card>
    )
}