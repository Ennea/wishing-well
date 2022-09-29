document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        VERSION: '1.3.3',

        // raw data from the backend
        bannerTypes: {},
        statistics: {},
        pity: [],
        lowPity: [],
        wishHistory: [],
        totalWishes: 0,

        // frontend and processed data
        dataLoaded: false,
        showUpdateNotification: false,
        backendStatus: 0,
        backendMessage: '',
        requestInProgress: false,
        wishHistoryURL: '',

        uidData: {},
        selectedUID: null,
        bannerTypesList: [],
        wishHistoryPageSize: 10,
        wishHistoryLastPage: 0,
        wishHistoryPage: 0,
        pagedWishHistory: [],

        uidSelectorOpen: false,
        availableUIDs: [],
        columnSettingsOpen: {
            rarity: false,
            type: false,
            bannerType: false
        },
        // filters consist of a key:value pair for every value a given
        // column can be filtered for. a value of true means that the
        // filter for that column value is enabled, aka being displayed
        // inside the table. the special __formatter key is for transforming
        // the name of the key into a proper value that the real data can
        // be compared against
        columnFilters: {
            rarity: {
                __formatter: (key) => parseInt(key.substring(1)),
                _3: true,
                _4: true,
                _5: true
            },
            type: {
                Character: true,
                Weapon: true
            },
            bannerType: {
                __formatter: (key) => parseInt(key.substring(1))
            }
        },

        // methods
        init() {
            this.$refs.dataContainer.classList.remove('hidden');
            this.loadData();

            // check if a newer version is available
            fetch('https://api.github.com/repos/Ennea/wishing-well/releases/latest').then((response) => {
                if (response.status == 200) {
                    return response.json();
                }
            }).then((json) => {
                if (json && this.versionToNumber(json.tag_name) > this.versionToNumber(this.VERSION)) {
                    this.showUpdateNotification = true;
                }
            });

            // register a click handler on the document;
            // this handles closing column settings and the uid
            // selector when the user clicks on anything else on
            // the page besides the currently open column settings
            // or uid selector
            document.addEventListener('click', (event) => {
                if (this.uidSelectorOpen && !this.$refs.uidSelectorOptions.contains(event.target)) {
                    this.uidSelectorOpen = false;
                }

                for (const [ column, isOpen ] of Object.entries(this.columnSettingsOpen)) {
                    if (isOpen && !this.$refs['columnSettings_' + column].contains(event.target)) {
                        this.columnSettingsOpen[column] = false;
                    }
                }
            });

            // set up watches for any data relevant to the filter for the wish history
            for (const [ column, keys ] of Object.entries(this.columnFilters)) {
                if (column == 'bannerType') {
                    continue;
                }
                for (const key of Object.keys(keys)) {
                    if (key == '__formatter') {
                        continue;
                    }
                    this.$watch(`columnFilters.${column}.${key}`, () => this.pageWishHistory());
                }
            }

            // set up heartbeat
            window.setInterval(() => {
                fetch('/heartbeat', { method: 'POST' });
            }, 10_000);
        },

        versionToNumber(version) {
            if (!version) {
                return null;
            }

            match = version.match(/^v?(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?$/);
            if (match == null) {
                return null;
            }

            version = parseInt(match[1]) * 1_0000 + parseInt(match[2]) * 1_00;
            if (match[3] != null) {
                version += parseInt(match[3]);
            }

            return version;
        },

        openModal() {
            document.body.classList.add('modal');
        },

        closeModal() {
            document.body.classList.remove('modal');
        },

        loadData() {
            fetch('/data', {
                cache: 'no-store'
            }).then((response) => {
                if (!response.ok) {
                    throw new Error();
                }
                return response.json();
            }).then((json) => {
                this.bannerTypes = json.bannerTypes;
                // create filters for the banner types and set up watches
                this.bannerTypesList = [];
                for (const [ key, name ] of Object.entries(this.bannerTypes)) {
                    this.bannerTypesList.push({ key, name });
                    if (!(key in this.columnFilters.bannerType)) {
                        this.$watch(`columnFilters.bannerType._${key}`, () => this.pageWishHistory());
                    }
                    this.columnFilters.bannerType[`_${key}`] = true;
                }

                this.uidData = json.uids;
                this.availableUIDs = Object.keys(this.uidData);
                // calculate percentages & limit decimal places of average pity for the statistics
                for (const [ _, data ] of Object.entries(this.uidData)) {
                    for (const [ _, category ] of Object.entries(data.statistics)) {
                        if (data.totalWishes > 0) {
                            category.percent = (category.total / data.totalWishes * 100);
                            if (parseInt(category.percent) != category.percent) {
                                category.percent = category.percent.toFixed(2);
                            }
                        } else {
                            category.percent = 0;
                        }

                        if ('averagePity' in category && parseInt(category.averagePity) != category.averagePity) {
                            category.averagePity = category.averagePity.toFixed(1);
                        }
                    }
                }

                if (Object.keys(this.uidData).length > 0) {
                    this.selectUID(Object.keys(this.uidData)[0]);
                }
                this.dataLoaded = true;
            });
        },

        updateWishes() {
            // reset message and status, show loading animation
            this.backendStatus = 0;
            this.backendMessage = '';
            this.requestInProgress = true;

            fetch('/update-wish-history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: '{}'
            }).then((response) => {
                return new Promise((resolve, reject) => {
                    response.json().then((json) => {
                        resolve({
                            status: response.status,
                            data: json
                        });
                    });
                });
            }, (error) => {
                this.backendStatus = 400;
                this.backendMessage = 'Connection failed! Try restarting Wishing Well.';
                throw error;
            }).then((json) => {
                this.backendStatus = json.status;
                this.backendMessage = json.data?.message || 'An unknown error has occurred.';
                this.loadData();
            }).finally(() => {
                this.requestInProgress = false;
            });
        },

        // page and filter the wish history for display
        pageWishHistory() {
            // first, turn our filters into lists
            const filters = {};
            for (const [ column, filter ] of Object.entries(this.columnFilters)) {
                const formatter = filter.__formatter ?? ((key) => key);
                filters[column] = [];
                for (const [ key, enabled ] of Object.entries(filter)) {
                    if (key == '__formatter') {
                        continue;
                    }
                    if (enabled) {
                        filters[column].push(formatter(key));
                    }
                }
            }

            // then, create a filtered copy of the wish history
            filteredWishHistory = this.wishHistory.filter((wish) => {
                let include = true;
                for (const [ column, permittedValues ] of Object.entries(filters)) {
                    if (!permittedValues.includes(wish[column])) {
                        include = false;
                        break;
                    }
                }
                return include;
            });

            // re-calculate last page based on filtered list
            this.wishHistoryLastPage = Math.max(0, Math.ceil(filteredWishHistory.length / this.wishHistoryPageSize) - 1);
            if (this.wishHistoryPage > this.wishHistoryLastPage) {
                this.wishHistoryPage = this.wishHistoryLastPage;
            }

            // grab the slice that is our current page
            this.pagedWishHistory = filteredWishHistory.slice(
                this.wishHistoryPage * this.wishHistoryPageSize,
                this.wishHistoryPage * this.wishHistoryPageSize + this.wishHistoryPageSize
            );

            // add empty entries to prevent visual jumps if length < pageSize
            while (this.pagedWishHistory.length < this.wishHistoryPageSize) {
                this.pagedWishHistory.push({
                    name: '–',
                    rarityText: '–',
                    type: '–',
                    bannerTypeName: '–',
                    time: '–'
                });
            }
        },

        firstPage() {
            this.wishHistoryPage = 0;
            this.pageWishHistory();
        },

        previousPage() {
            this.wishHistoryPage = Math.max(0, this.wishHistoryPage - 1);
            this.pageWishHistory();
        },

        nextPage() {
            this.wishHistoryPage = Math.min(this.wishHistoryLastPage, this.wishHistoryPage + 1);
            this.pageWishHistory();
        },

        lastPage() {
            this.wishHistoryPage = this.wishHistoryLastPage;
            this.pageWishHistory();
        },

        toggleColumnSettings(event, column) {
            event.stopPropagation();
            this.columnSettingsOpen[column] = !this.columnSettingsOpen[column];

            // hide uid selector if it's open
            if (this.uidSelectorOpen) {
                this.uidSelectorOpen = false;
            }

            // hide any other open settings
            if (this.columnSettingsOpen[column]) {
                for (const [ key, isOpen ] of Object.entries(this.columnSettingsOpen)) {
                    if (key != column && isOpen) {
                        this.columnSettingsOpen[key] = false;
                    }
                }
            }
        },

        // helper method, because dynamically setting x-model inside x-for does not seem to work (?)
        bannerTypeFilterChange(event, bannerType) {
            this.columnFilters.bannerType[`_${bannerType}`] = event.target.checked;
        },

        toggleUIDSelector(event) {
            event.stopPropagation();
            this.uidSelectorOpen = !this.uidSelectorOpen;

            // hide any open column settings
            for (const [ key, isOpen ] of Object.entries(this.columnSettingsOpen)) {
                if (isOpen) {
                    this.columnSettingsOpen[key] = false;
                }
            }
        },

        selectUID(uid) {
            this.$refs.uidSelector._x_model.set(uid);
            this.uidSelectorOpen = false;

            this.statistics = this.uidData[uid].statistics;
            this.pity = this.uidData[uid].pity;
            this.lowPity = this.uidData[uid].lowPity;
            this.wishHistory = this.uidData[uid].wishHistory;
            this.totalWishes = this.uidData[uid].totalWishes;

            this.wishHistoryPage = 0;
            this.pageWishHistory();
        }
    }));
});
