package binary

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Packet(ctx *CTX_Packet, req *REQ_Packet) (rsp *RSP_Packet, err error) {
	packet := req.B
	itemIDs := make([]uint, 0, len(packet.Body.Items))
	firstLabel := ""
	for index, item := range packet.Body.Items {
		itemIDs = append(itemIDs, uint(item.ID))
		if index == 0 {
			firstLabel = string(item.Label)
		}
	}

	var scoreSum float64
	for _, score := range packet.Body.Scores {
		scoreSum += score
	}

	trace := ""
	if req.Q != nil {
		trace = req.Q.Trace
	}

	return &RSP_Packet{
		Trace:      trace,
		Version:    uint(packet.Header.Version),
		ItemCount:  uint(packet.Header.ItemCount),
		Payload:    string(packet.Body.Payload),
		ScoreSum:   scoreSum,
		FirstLabel: firstLabel,
		ItemIds:    itemIDs,
		Checksum:   uint(packet.Body.Checksum),
	}, nil
}
