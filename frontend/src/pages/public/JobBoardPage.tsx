import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPublicJobs } from "@/services/jobs";
import type { JobPublicRead } from "@/types/api";
import axios from "axios";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "…";
}

export default function JobBoardPage() {
  const [jobs, setJobs] = useState<JobPublicRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchJobs() {
      try {
        const data = await getPublicJobs();
        if (!cancelled) setJobs(data);
      } catch (err) {
        if (!cancelled) {
          if (axios.isAxiosError(err)) {
            setError("Failed to load jobs. Please try again later.");
          } else {
            setError("An unexpected error occurred.");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-gray-400">Loading jobs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-6 text-center text-red-700">{error}</div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Open Positions</h1>
        <p className="mt-2 text-gray-600">
          Browse our current job openings and apply today.
        </p>
      </div>

      {jobs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 py-24 text-center text-gray-400">
          No open positions at this time. Check back soon.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
          {jobs.map((job) => (
            <Link
              key={job.id}
              to={`/jobs/${job.id}`}
              className="group block rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition hover:border-blue-300 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold text-gray-900 group-hover:text-blue-600">
                    {job.title}
                  </h2>
                  <p className="mt-1 text-sm text-gray-500">{job.location}</p>
                </div>
                <span className="shrink-0 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                  Open
                </span>
              </div>
              <p className="mt-3 text-sm text-gray-600">
                {truncate(job.description, 160)}
              </p>
              <p className="mt-4 text-xs text-gray-400">
                Posted {formatDate(job.created_at)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
