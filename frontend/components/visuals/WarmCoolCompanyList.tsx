import { CompanyChip } from "./CompanyChip";

export function WarmCoolCompanyList({
  label,
  dotClass,
  companies,
}: {
  label: string;
  dotClass: string;
  companies: string[];
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-[11px] text-neutral-grey-20">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} /> {label}
      </span>
      <div className="flex flex-wrap gap-1.5 pl-3.5">
        {companies.map((c) => (
          <CompanyChip key={c} company={c} />
        ))}
      </div>
    </div>
  );
}
