import { API_BASE_URL } from '$lib/config';

export type StatsRangeValue = 'short_term' | 'medium_term' | 'long_term';

export const rangeOptions: { label: string; value: StatsRangeValue }[] = [
	{ label: '4 Weeks', value: 'short_term' },
	{ label: '6 Months', value: 'medium_term' },
	{ label: 'All Time', value: 'long_term' }
];

export type MusicSource = 'spotify' | 'spotify_derived' | 'captured';

export type DashboardSummary = {
	totalMinutes: number | null;
	currentArtist: string | null;
	currentArtistImageUrl: string | null;
};

export type Artist = {
	spotifyArtistId?: string;
	name: string;
	plays?: number;
	listeningMinutes?: number;
	imageUrl: string | null;
	externalUrl?: string | null;
	spotifyRank?: number;
	topTrackCount?: number;
	source?: MusicSource;
};

export type Track = {
	spotifyTrackId?: string;
	title: string;
	artist: string;
	album: string;
	plays?: number;
	listeningMinutes?: number;
	coverUrl: string | null;
	externalUrl?: string | null;
	spotifyRank?: number;
	source?: MusicSource;
};

export type Album = {
	spotifyAlbumId?: string;
	title: string;
	artist: string;
	plays?: number;
	listeningMinutes?: number;
	coverUrl: string | null;
	externalUrl?: string | null;
	spotifyRank?: number;
	topTrackCount?: number;
	source?: MusicSource;
};

export type TimeOfDayMetric = {
	label: string;
	value: number;
	listeningMinutes?: number;
};

export type MusicalDnaMetric = {
	label: string;
	value: string;
	glyph: 'bolt' | 'tempo' | 'mood';
};

export type SyncRun = {
	id: number;
	status: string;
	fetchedCount: number;
	insertedCount: number;
	startedAt: string;
	completedAt: string | null;
	errorMessage: string | null;
};

type RecapResponse = {
	summary: DashboardSummary;
	timeOfDay: TimeOfDayMetric[];
};

type SpotifyTopResponse = {
	range?: StatsRangeValue;
	Range?: StatsRangeValue;
	tracks?: Track[];
	Tracks?: Track[];
	artists?: Artist[];
	Artists?: Artist[];
	albums?: Album[];
	Albums?: Album[];
};

const DEFAULT_RANGE: StatsRangeValue = 'short_term';

export const dashboardSummary: DashboardSummary = {
	totalMinutes: null,
	currentArtist: null,
	currentArtistImageUrl: null
};

export const artists: Artist[] = [];
export const tracks: Track[] = [];
export const albums: Album[] = [];
export const musicalDna: MusicalDnaMetric[] = [];

let latestMusicRequestId = 0;

export async function loadMusicData(range: StatsRangeValue = DEFAULT_RANGE) {
	const requestId = ++latestMusicRequestId;
	const query = `range=${encodeURIComponent(range)}`;
	const [recap, spotifyTop] = await Promise.all([
		fetchJson<RecapResponse>(`/api/stats/recap?${query}`).catch(() => createEmptyRecap()),
		fetchJson<SpotifyTopResponse>(`/api/spotify/top?${query}&limit=50`)
	]);

	if (requestId !== latestMusicRequestId) {
		return;
	}

	Object.assign(dashboardSummary, recap.summary ?? createEmptyDashboardSummary());
	replaceArray(tracks, spotifyTop.tracks ?? spotifyTop.Tracks ?? []);
	replaceArray(artists, spotifyTop.artists ?? spotifyTop.Artists ?? []);
	replaceArray(albums, spotifyTop.albums ?? spotifyTop.Albums ?? []);
	replaceArray(musicalDna, buildMusicalDna(recap));
}

export async function syncListeningHistory(force = false) {
	return fetchJson<SyncRun>(`/api/sync/spotify/recently-played${force ? '?force=true' : ''}`, {
		method: 'POST'
	});
}

async function fetchJson<T>(path: string, init: RequestInit = {}) {
	const response = await fetch(`${API_BASE_URL}${path}`, {
		...init,
		credentials: 'include',
		headers: {
			Accept: 'application/json',
			...init.headers
		}
	});

	if (!response.ok) {
		const detail = await response
			.clone()
			.json()
			.then((body) => (body && typeof body.detail === 'string' ? body.detail : null))
			.catch(() => null);
		throw new Error(detail ?? `Request failed with status ${response.status}`);
	}

	return (await response.json()) as T;
}

export type ProposedTrack = Track & { reason?: string };

export type ProposedPlaylist = {
	generationId: string;
	name: string;
	description: string;
	tracks: ProposedTrack[];
	trackUris: string[];
};

export type GeneratePlaylistInput = {
	prompt: string;
	length: number;
	mix: number;
	allowExplicit: boolean;
	range: StatsRangeValue;
};

export async function generatePlaylist(input: GeneratePlaylistInput) {
	return fetchJson<ProposedPlaylist>('/api/ai/playlist/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(input)
	});
}

export type CommitPlaylistResult = {
	playlistId: string;
	spotifyUrl: string | null;
	trackCount: number;
};

export async function commitPlaylist(generationId: string, isPublic = false) {
	return fetchJson<CommitPlaylistResult>('/api/ai/playlist/commit', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ generationId, isPublic })
	});
}

function replaceArray<T>(target: T[], next: T[]) {
	target.splice(0, target.length, ...next);
}

function createEmptyDashboardSummary(): DashboardSummary {
	return {
		totalMinutes: null,
		currentArtist: null,
		currentArtistImageUrl: null
	};
}

function createEmptyRecap(): RecapResponse {
	return {
		summary: createEmptyDashboardSummary(),
		timeOfDay: []
	};
}

function buildMusicalDna(recap: RecapResponse): MusicalDnaMetric[] {
	const peakWindow = recap.timeOfDay
		.filter((item) => item.listeningMinutes && item.listeningMinutes > 0)
		.sort((a, b) => (b.listeningMinutes ?? 0) - (a.listeningMinutes ?? 0))[0];

	const metrics: MusicalDnaMetric[] = [];

	if (dashboardSummary.totalMinutes !== null) {
		metrics.push({
			label: 'Minutes logged',
			value: dashboardSummary.totalMinutes.toLocaleString(),
			glyph: 'bolt'
		});
	}

	if (peakWindow) {
		metrics.push({
			label: 'Peak window',
			value: peakWindow.label,
			glyph: 'tempo'
		});
	}

	return metrics;
}
