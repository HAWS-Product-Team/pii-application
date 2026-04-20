import Card from "./Card";

export default function HighestInflationCard() {
  return (
    <Card className="p-4 w-96 bg-[#77B3B3] rounded-lg text-white">
      <p className="text-lg font-medium">Highest inflation</p>
      <p className="text-2xl pt-8 font-semibold mt-1">Groceries</p>
      <p className="text-3xl font-bold mt-0.5">+3.45%</p>
    </Card>
  );
}