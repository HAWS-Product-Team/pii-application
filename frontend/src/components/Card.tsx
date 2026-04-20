
interface CardProps {
  children: React.ReactNode;
  className?: string;
}

const Card = ({children, className=""}: CardProps) => (
    <div className={`opacity-65 drop-shadow-xl ${className}`}>
        {children}
    </div>
)

export default Card;