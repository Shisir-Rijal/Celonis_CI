"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { getCompetitorColor } from "@/lib/competitors/colors";
import { useCompetitorColors } from "@/lib/competitors/hooks";

export type DateRange = "all" | "7d" | "30d" | "3m";
export type SourceType = "all" | "firecrawl" | "finnhub" | "serper";

const DATE_RANGE_OPTIONS: { value: DateRange; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "3m", label: "Last 3 months" },
];

const SOURCE_OPTIONS: { value: SourceType; label: string }[] = [
  { value: "all", label: "All sources" },
  { value: "firecrawl", label: "Official" },
  { value: "finnhub", label: "Financial News" },
  { value: "serper", label: "Media Coverage" },
];

type CompanyOption = {
  domain: string;
  name: string;
};

type DropdownProps = {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
};

function Dropdown({ label, value, options, onChange }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full border border-white/15 text-neutral-grey-10 hover:border-white/30 transition-colors"
      >
        <span className="text-neutral-grey-20">{label}:</span>
        <span className="text-primary-white">{selected?.label}</span>
        <ChevronDown size={11} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[160px] bg-neutral-grey-30 border border-white/10 rounded-lg overflow-hidden shadow-lg">
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              className={`w-full text-left px-4 py-2 text-xs transition-colors hover:bg-white/8 ${
                opt.value === value
                  ? "text-secondary-green font-medium"
                  : "text-neutral-grey-10"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type NewsFiltersProps = {
  companyOptions: CompanyOption[];
  selectedCompanies: string[];
  onCompaniesChange: (next: string[]) => void;
  dateRange: DateRange;
  onDateRangeChange: (next: DateRange) => void;
  selectedSource: SourceType;
  onSourceChange: (next: SourceType) => void;
  availableTopics: string[];
  selectedTopic: string;
  onTopicChange: (next: string) => void;
};

export default function NewsFilters({
  companyOptions,
  selectedCompanies,
  onCompaniesChange,
  dateRange,
  onDateRangeChange,
  selectedSource,
  onSourceChange,
  availableTopics,
  selectedTopic,
  onTopicChange,
}: NewsFiltersProps) {
  const { data: brandColors = {} } = useCompetitorColors();
  const allDomains = companyOptions.map((o) => o.domain);
  const isAllSelected = selectedCompanies.length === 0;

  function toggleCompany(domain: string) {
    if (selectedCompanies.includes(domain)) {
      onCompaniesChange(selectedCompanies.filter((d) => d !== domain));
    } else {
      onCompaniesChange([...selectedCompanies, domain]);
    }
  }

  const topicOptions = [
    { value: "all", label: "All topics" },
    ...availableTopics.map((t) => ({ value: t, label: t })),
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* Company chips */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onCompaniesChange([])}
          className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-colors ${
            isAllSelected
              ? "bg-secondary-green text-primary-black border-secondary-green"
              : "bg-transparent text-neutral-grey-10 border-white/15 hover:border-white/30"
          }`}
        >
          All
        </button>
        {companyOptions.map((opt) => {
          const isSelected = selectedCompanies.includes(opt.domain);
          const color = getCompetitorColor(opt.domain, allDomains, brandColors);
          return (
            <button
              key={opt.domain}
              type="button"
              onClick={() => toggleCompany(opt.domain)}
              className="text-xs font-medium px-3 py-1.5 rounded-full border transition-colors"
              style={
                isSelected
                  ? { backgroundColor: `${color}26`, color, borderColor: color }
                  : { color: "#CBCBCB", borderColor: "rgba(255,255,255,0.15)" }
              }
            >
              {opt.name}{isSelected && " ✓"}
            </button>
          );
        })}
      </div>

      {/* Period + Source + Topic dropdowns */}
      <div className="flex items-center gap-3 flex-wrap">
        <Dropdown
          label="Period"
          value={dateRange}
          options={DATE_RANGE_OPTIONS}
          onChange={(v) => onDateRangeChange(v as DateRange)}
        />
        <Dropdown
          label="Source"
          value={selectedSource}
          options={SOURCE_OPTIONS}
          onChange={(v) => onSourceChange(v as SourceType)}
        />
        {availableTopics.length > 0 && (
          <Dropdown
            label="Topic"
            value={selectedTopic}
            options={topicOptions}
            onChange={onTopicChange}
          />
        )}
      </div>
    </div>
  );
}