def _extract_arrays(self, keys):
        h, s, T, p = [], [], [], []
        for k in keys:
            if k is None:
                # np.nan zwingt Plotly garantiert dazu, die Linie hier abzusetzen!
                h.append(np.nan)
                s.append(np.nan)
                T.append(np.nan)
                p.append(np.nan)
            else:
                h.append(self.zustand[k]['h']/1000)
                s.append(self.zustand[k]['s']/1000)
                T.append(self.zustand[k]['T']-273.15)
                p.append(self.zustand[k]['p']/100000)
        return h, s, T, p
