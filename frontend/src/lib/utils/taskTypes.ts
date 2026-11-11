/**
 * Processing task types as the UI names them, and which of them only an LLM runs.
 *
 * One table for every surface that lists tasks (status grid, file detail modal,
 * admin statistics), so a type never borrows another type's label and an
 * LLM-only stage is hidden the same way everywhere when no LLM is configured.
 */

/** Stages that exist only with an LLM provider (summary, topics, AI speaker naming). */
export const LLM_TASK_TYPES: ReadonlySet<string> = new Set([
  'summarization',
  'topic_extraction',
  'speaker_identification',
]);

const TASK_TYPE_LABEL_KEYS: Readonly<Record<string, string>> = {
  transcription: 'fileStatus.transcription',
  search_indexing: 'search.settingsTitle',
  summarization: 'fileStatus.summarization',
  analytics: 'reprocess.stageAnalytics',
  topic_extraction: 'reprocess.stageTopicExtraction',
  speaker_identification: 'reprocess.stageSpeakerLLM',
  speaker_embedding: 'fileStatus.speakerProcessing',
  speaker_attribute_detection: 'fileStatus.speakerProcessing',
  speaker_clustering: 'fileStatus.speakerProcessing',
};

/** Translated label of a task type; an unknown type shows its raw name. */
export function taskTypeLabel(taskType: string, translate: (key: string) => string): string {
  const key = TASK_TYPE_LABEL_KEYS[taskType];
  return key ? translate(key) : taskType;
}

/** Task rows a deployment can act on: LLM-only stages drop out when no LLM exists. */
export function visibleTasks<T extends { task_type: string }>(tasks: T[], llmAvailable: boolean): T[] {
  return llmAvailable ? tasks : tasks.filter((task) => !LLM_TASK_TYPES.has(task.task_type));
}
