import { useEffect, useState } from "react";
import "./Thinking.css";

interface Props {
  company: string;
}

const sentences = (company: string) => [
  `Reading about ${company}…`,
  `Finding the people you’ll meet…`,
  `Looking at what’s happened recently…`,
  `Assembling your brief.`,
];

export default function Thinking({ company }: Props) {
  const lines = sentences(company);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setIndex((i) => Math.min(i + 1, lines.length - 1));
    }, 3400);
    return () => window.clearInterval(id);
  }, [lines.length]);

  return (
    <main className="view thinking">
      <p className="thinking__line" key={index}>
        {lines[index]}
      </p>
    </main>
  );
}
