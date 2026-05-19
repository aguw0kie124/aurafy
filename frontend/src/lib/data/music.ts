import { API_BASE_URL } from '$lib/config';

export type DashboardSummary = {
	totalMinutes: number | null;
	artistsDiscovered: number | null;
	currentArtist: string | null;
	currentRank: number | null;
	currentArtistImageUrl: string | null;
	totalPlays?: number;
	uniqueTracks?: number;
	lastPlayedAt?: string | null;
	lastSyncedAt?: string | null;
};

export type Artist = {
	spotifyArtistId?: string;
	name: string;
	plays: number;
	listeningMinutes?: number;
	imageUrl: string | null;
	externalUrl?: string | null;
};

export type Track = {
	spotifyTrackId?: string;
	title: string;
	artist: string;
	album: string;
	plays: number;
	listeningMinutes?: number;
	coverUrl: string | null;
	externalUrl?: string | null;
};

export type Album = {
	spotifyAlbumId?: string;
	title: string;
	artist: string;
	plays: number;
	listeningMinutes?: number;
	coverUrl: string | null;
	externalUrl?: string | null;
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
	topTracks: Track[];
	topArtists: Artist[];
	topAlbums: Album[];
	timeOfDay: TimeOfDayMetric[];
};

const DEFAULT_RANGE = 'short_term';

export const dashboardSummary: DashboardSummary = {
	totalMinutes: null,
	artistsDiscovered: null,
	currentArtist: null,
	currentRank: null,
	currentArtistImageUrl: null
};

export const artists: Artist[] = [];
export const tracks: Track[] = [];
export const albums: Album[] = [];
export const musicalDna: MusicalDnaMetric[] = [];

export async function loadMusicData(range = DEFAULT_RANGE) {
	const query = `range=${encodeURIComponent(range)}`;
	const [summary, topTracks, topArtists, topAlbums, recap] = await Promise.all([
		fetchJson<DashboardSummary>(`/api/stats/dashboard?${query}`),
		fetchJson<Track[]>(`/api/stats/tracks?${query}&limit=25`),
		fetchJson<Artist[]>(`/api/stats/artists?${query}&limit=25`),
		fetchJson<Album[]>(`/api/stats/albums?${query}&limit=25`),
		fetchJson<RecapResponse>(`/api/stats/recap?${query}`)
	]);

	Object.assign(dashboardSummary, summary);
	replaceArray(tracks, topTracks.map(normalizeTrack));
	replaceArray(artists, topArtists);
	replaceArray(albums, topAlbums.map(normalizeAlbum));
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
		throw new Error(`Request failed with status ${response.status}`);
	}

	return (await response.json()) as T;
}

function replaceArray<T>(target: T[], next: T[]) {
	target.splice(0, target.length, ...next);
}

function normalizeTrack(track: Track): Track {
	return {
		...track,
		album: track.album ?? 'Unknown album'
	};
}

function normalizeAlbum(album: Album): Album {
	return {
		...album,
		artist: album.artist ?? 'Unknown artist'
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
