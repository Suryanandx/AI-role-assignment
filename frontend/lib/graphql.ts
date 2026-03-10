import { request, gql } from "graphql-request";

const graphqlUrl =
  process.env.NEXT_PUBLIC_GRAPHQL_URL ?? "http://localhost:8000/graphql";

export type JobResult = {
  id: string;
  status: string;
  topic: string;
} | null;

export type ArticleSection = { level: number; heading: string; content: string };
export type SEOMetadata = {
  title_tag: string;
  meta_description: string;
  primary_keyword: string;
  secondary_keywords: string[];
};
export type InternalLink = { anchor_text: string; target_topic: string };
export type ExternalRef = {
  url: string;
  title: string;
  placement_context: string;
};
export type FAQItem = { question: string; answer: string };

export type JobFull = {
  id: string;
  status: string;
  topic: string;
  word_count: number;
  language: string;
  current_step: string | null;
  quality_score: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  article: { sections: ArticleSection[] } | null;
  metadata: SEOMetadata | null;
  internal_links: InternalLink[];
  external_refs: ExternalRef[];
  faq: FAQItem[] | null;
  article_with_faq: {
    sections: ArticleSection[];
    faq: FAQItem[];
  } | null;
} | null;

const JobQuery = gql`
  query Job($id: ID!) {
    job(id: $id) {
      id
      status
      topic
    }
  }
`;

const JobFullQuery = gql`
  query JobFull($id: ID!) {
    job(id: $id) {
      id
      status
      topic
      wordCount
      language
      currentStep
      qualityScore
      error
      createdAt
      updatedAt
      article {
        sections {
          level
          heading
          content
        }
      }
      metadata {
        titleTag
        metaDescription
        primaryKeyword
        secondaryKeywords
      }
      internalLinks {
        anchorText
        targetTopic
      }
      externalRefs {
        url
        title
        placementContext
      }
      faq {
        question
        answer
      }
      articleWithFaq {
        sections {
          level
          heading
          content
        }
        faq {
          question
          answer
        }
      }
    }
  }
`;

const CreateJobMutation = gql`
  mutation CreateJob($input: CreateJobInput!) {
    createJob(input: $input)
  }
`;

const RetryJobMutation = gql`
  mutation RetryJob($jobId: ID!) {
    retryJob(jobId: $jobId) {
      id
      status
      topic
      wordCount
      language
      currentStep
      qualityScore
      error
      createdAt
      updatedAt
      article {
        sections {
          level
          heading
          content
        }
      }
      metadata {
        titleTag
        metaDescription
        primaryKeyword
        secondaryKeywords
      }
      internalLinks {
        anchorText
        targetTopic
      }
      externalRefs {
        url
        title
        placementContext
      }
      faq {
        question
        answer
      }
      articleWithFaq {
        sections {
          level
          heading
          content
        }
        faq {
          question
          answer
        }
      }
    }
  }
`;

const RunPipelineMutation = gql`
  mutation RunPipeline($jobId: ID!) {
    runPipeline(jobId: $jobId) {
      id
      status
      topic
      wordCount
      language
      currentStep
      qualityScore
      error
      createdAt
      updatedAt
      article {
        sections {
          level
          heading
          content
        }
      }
      metadata {
        titleTag
        metaDescription
        primaryKeyword
        secondaryKeywords
      }
      internalLinks {
        anchorText
        targetTopic
      }
      externalRefs {
        url
        title
        placementContext
      }
      faq {
        question
        answer
      }
      articleWithFaq {
        sections {
          level
          heading
          content
        }
        faq {
          question
          answer
        }
      }
    }
  }
`;

type JobFullRaw = {
  id: string;
  status: string;
  topic: string;
  wordCount: number;
  language: string;
  currentStep: string | null;
  qualityScore: number | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  article: { sections: { level: number; heading: string; content: string }[] } | null;
  metadata: {
    titleTag: string;
    metaDescription: string;
    primaryKeyword: string;
    secondaryKeywords: string[];
  } | null;
  internalLinks: { anchorText: string; targetTopic: string }[];
  externalRefs: { url: string; title: string; placementContext: string }[];
  faq: { question: string; answer: string }[] | null;
  articleWithFaq: {
    sections: { level: number; heading: string; content: string }[];
    faq: { question: string; answer: string }[];
  } | null;
};

function mapJobFull(raw: JobFullRaw): JobFull {
  return {
    id: raw.id,
    status: raw.status,
    topic: raw.topic,
    word_count: raw.wordCount,
    language: raw.language,
    current_step: raw.currentStep,
    quality_score: raw.qualityScore,
    error: raw.error,
    created_at: raw.createdAt,
    updated_at: raw.updatedAt,
    article: raw.article ? { sections: raw.article.sections } : null,
    metadata: raw.metadata
      ? {
          title_tag: raw.metadata.titleTag,
          meta_description: raw.metadata.metaDescription,
          primary_keyword: raw.metadata.primaryKeyword,
          secondary_keywords: raw.metadata.secondaryKeywords ?? [],
        }
      : null,
    internal_links: (raw.internalLinks ?? []).map((l) => ({
      anchor_text: l.anchorText,
      target_topic: l.targetTopic,
    })),
    external_refs: (raw.externalRefs ?? []).map((r) => ({
      url: r.url,
      title: r.title,
      placement_context: r.placementContext,
    })),
    faq: raw.faq ?? null,
    article_with_faq: raw.articleWithFaq
      ? {
          sections: raw.articleWithFaq.sections,
          faq: raw.articleWithFaq.faq ?? [],
        }
      : null,
  };
}

export async function getJob(id: string): Promise<JobResult> {
  const data = await request<{ job: JobResult }>(graphqlUrl, JobQuery, {
    id,
  });
  return data.job;
}

export async function getJobFull(id: string): Promise<JobFull> {
  const data = await request<{ job: JobFullRaw | null }>(
    graphqlUrl,
    JobFullQuery,
    { id }
  );
  const job = data.job;
  if (!job) return null;
  return mapJobFull(job);
}

export async function createJob(params: {
  topic: string;
  word_count?: number;
  language?: string;
}): Promise<string> {
  const data = await request<{ createJob: string }>(graphqlUrl, CreateJobMutation, {
    input: {
      topic: params.topic,
      wordCount: params.word_count ?? 1500,
      language: params.language ?? "en",
    },
  });
  return data.createJob;
}

export async function runPipeline(jobId: string): Promise<JobFull> {
  const data = await request<{
    runPipeline: JobFullRaw | null;
  }>(graphqlUrl, RunPipelineMutation, { jobId });
  const job = data.runPipeline;
  if (!job) return null;
  return mapJobFull(job);
}

export async function retryJob(jobId: string): Promise<JobFull> {
  const data = await request<{
    retryJob: JobFullRaw | null;
  }>(graphqlUrl, RetryJobMutation, { jobId });
  const job = data.retryJob;
  if (!job) return null;
  return mapJobFull(job);
}
