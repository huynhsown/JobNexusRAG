import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Briefcase, X } from "lucide-react";
import { Button } from "./button";
import { Input } from "./input";
import { Select } from "./select";
import { Textarea } from "./textarea";
import { cn } from "@/lib/utils";
import type { Company } from "@/types";

type EmploymentType =
  | "full_time"
  | "part_time"
  | "contract"
  | "internship"
  | "remote";

export interface CreateJobFormValues {
  company_id: number;
  title: string;
  description_text?: string;
  location?: string;
  salary_min?: number;
  salary_max?: number;
  experience_required?: number;
  skills_required?: string[];
  skills_nice_to_have?: string[];
  employment_type: EmploymentType;
}

interface CreateJobDialogProps {
  open: boolean;
  companies: Company[] | undefined;
  defaultCompanyId?: number;
  onCancel: () => void;
  onSubmit: (values: CreateJobFormValues) => void;
  submitting?: boolean;
}

function parseCsvList(raw: string): string[] | undefined {
  const list = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return list.length ? Array.from(new Set(list)) : undefined;
}

function parseOptionalNumber(raw: string): number | undefined {
  const v = raw.trim();
  if (!v) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export const CreateJobDialog = memo(function CreateJobDialog({
  open,
  companies,
  defaultCompanyId,
  onCancel,
  onSubmit,
  submitting = false,
}: CreateJobDialogProps) {
  const titleRef = useRef<HTMLInputElement>(null);
  const companyOptions = companies ?? [];

  const initialCompanyId = useMemo(() => {
    if (defaultCompanyId && companyOptions.some((c) => c.id === defaultCompanyId)) {
      return defaultCompanyId;
    }
    return companyOptions[0]?.id ?? 0;
  }, [companyOptions, defaultCompanyId]);

  const [companyId, setCompanyId] = useState<number>(initialCompanyId);
  const [title, setTitle] = useState("");
  const [descriptionText, setDescriptionText] = useState("");
  const [location, setLocation] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [experienceRequired, setExperienceRequired] = useState("");
  const [skillsRequired, setSkillsRequired] = useState("");
  const [skillsNiceToHave, setSkillsNiceToHave] = useState("");
  const [employmentType, setEmploymentType] = useState<EmploymentType>("full_time");

  useEffect(() => {
    if (!open) return;
    setCompanyId(initialCompanyId);
    setTitle("");
    setDescriptionText("");
    setLocation("");
    setSalaryMin("");
    setSalaryMax("");
    setExperienceRequired("");
    setSkillsRequired("");
    setSkillsNiceToHave("");
    setEmploymentType("full_time");
    const t = window.setTimeout(() => titleRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open, initialCompanyId]);

  const canSubmit = Boolean(title.trim()) && companyId > 0 && !submitting;

  const submit = useCallback(() => {
    if (!canSubmit) return;

    const values: CreateJobFormValues = {
      company_id: companyId,
      title: title.trim(),
      description_text: descriptionText.trim() || undefined,
      location: location.trim() || undefined,
      salary_min: parseOptionalNumber(salaryMin),
      salary_max: parseOptionalNumber(salaryMax),
      experience_required: parseOptionalNumber(experienceRequired),
      skills_required: parseCsvList(skillsRequired),
      skills_nice_to_have: parseCsvList(skillsNiceToHave),
      employment_type: employmentType,
    };

    onSubmit(values);
  }, [
    canSubmit,
    companyId,
    title,
    descriptionText,
    location,
    salaryMin,
    salaryMax,
    experienceRequired,
    skillsRequired,
    skillsNiceToHave,
    employmentType,
    onSubmit,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submit();
    },
    [onCancel, submit]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onKeyDown={handleKeyDown}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onCancel}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-job-title"
        className="relative z-10 w-full max-w-2xl mx-4 rounded-xl bg-card border border-border shadow-2xl animate-in zoom-in-95 fade-in duration-200"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
              <Briefcase className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h3 id="create-job-title" className="text-lg font-semibold leading-tight">
                Create job
              </h3>
              <p className="text-xs text-muted-foreground">
                Fill the fields to match backend schema.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="p-2 rounded-md hover:bg-muted"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Company</div>
              <Select
                value={String(companyId)}
                onChange={(e) => setCompanyId(Number(e.target.value))}
                disabled={companyOptions.length === 0}
              >
                {companyOptions.length === 0 ? (
                  <option value="0">No companies yet</option>
                ) : null}
                {companyOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-1.5">
              <div className="text-xs font-medium">Employment type</div>
              <Select
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value as EmploymentType)}
              >
                <option value="full_time">Full time</option>
                <option value="part_time">Part time</option>
                <option value="contract">Contract</option>
                <option value="internship">Internship</option>
                <option value="remote">Remote</option>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="text-xs font-medium">Title</div>
            <Input
              ref={titleRef}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Backend Engineer"
            />
          </div>

          <div className="space-y-1.5">
            <div className="text-xs font-medium">Description text</div>
            <Textarea
              value={descriptionText}
              onChange={(e) => setDescriptionText(e.target.value)}
              placeholder="Paste the job description (optional, but recommended)."
              className="min-h-[140px]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Location</div>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Ho Chi Minh City"
              />
            </div>
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Experience required (years)</div>
              <Input
                value={experienceRequired}
                onChange={(e) => setExperienceRequired(e.target.value)}
                placeholder="e.g. 3"
                inputMode="decimal"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Salary min</div>
              <Input
                value={salaryMin}
                onChange={(e) => setSalaryMin(e.target.value)}
                placeholder="e.g. 1000"
                inputMode="decimal"
              />
            </div>
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Salary max</div>
              <Input
                value={salaryMax}
                onChange={(e) => setSalaryMax(e.target.value)}
                placeholder="e.g. 2000"
                inputMode="decimal"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Skills required</div>
              <Input
                value={skillsRequired}
                onChange={(e) => setSkillsRequired(e.target.value)}
                placeholder="e.g. React, TypeScript, REST"
              />
              <div className="text-[11px] text-muted-foreground">
                Comma-separated list.
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="text-xs font-medium">Skills nice to have</div>
              <Input
                value={skillsNiceToHave}
                onChange={(e) => setSkillsNiceToHave(e.target.value)}
                placeholder="e.g. GraphQL, Docker"
              />
              <div className="text-[11px] text-muted-foreground">
                Comma-separated list.
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-border/50 bg-muted/20 rounded-b-xl">
          <div className={cn("text-xs text-muted-foreground", !canSubmit && "opacity-70")}>
            Tip: press <span className="font-medium">Ctrl/⌘ + Enter</span> to create
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
            <Button size="sm" onClick={submit} disabled={!canSubmit}>
              {submitting ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
});

