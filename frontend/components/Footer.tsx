import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import Image from "next/image";

export default function Footer() {
  return (
    <section
        className={twMerge(
            clsx(
            "bg-primary-black flex flex-col gap-4 px-16 py-8",
            )
        )}
    >
        <h3 className="text-primary-white">Copyright {new Date().getFullYear()} ©</h3>
        <p className="text-neutral-grey-20">Celonis x MucDai</p>
    </section>
  );
}
