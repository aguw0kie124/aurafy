export type DashboardSummary = {
	totalMinutes: number | null;
	artistsDiscovered: number | null;
	topGenre: string | null;
	currentArtist: string | null;
	currentRank: number | null;
	currentArtistImageUrl: string | null;
};

export type Artist = {
	name: string;
	plays: number;
	imageUrl: string | null;
};

export type Track = {
	title: string;
	artist: string;
	album: string;
	plays: number;
	coverUrl: string | null;
};

export type Album = {
	title: string;
	artist: string;
	plays: number;
	coverUrl: string | null;
};

export type TasteMetric = {
	label: string;
	value: number;
};

export type GenreMetric = {
	label: string;
	value: number;
};

export type MusicalDnaMetric = {
	label: string;
	value: string;
	glyph: 'bolt' | 'tempo' | 'mood';
};

export const dashboardSummary: DashboardSummary = {
	totalMinutes: null,
	artistsDiscovered: null,
	topGenre: null,
	currentArtist: null,
	currentRank: null,
	currentArtistImageUrl: null
};

export const artists: Artist[] = [];
export const tracks: Track[] = [];
export const albums: Album[] = [];
export const tasteProfile: TasteMetric[] = [];
export const genres: GenreMetric[] = [];
export const musicalDna: MusicalDnaMetric[] = [];
