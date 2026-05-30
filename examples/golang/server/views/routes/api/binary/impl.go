package binary

import binaryschema "example.com/project/golang/server/views/routes/api/binary/_gen_binary"

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

func (impl *Router) AuditPacket(ctx *CTX_AuditPacket, req *REQ_AuditPacket) (rsp *RSP_AuditPacket, err error) {
	packet := req.B
	trace := ""
	if req.Q != nil {
		trace = req.Q.Trace
	}
	return &RSP_AuditPacket{
		Trace:     trace,
		ItemCount: uint(packet.Header.ItemCount),
		Checksum:  uint(packet.Body.Checksum),
	}, nil
}

func (impl *Router) WidePacket(ctx *CTX_WidePacket, req *REQ_WidePacket) (rsp *RSP_WidePacket, err error) {
	packet := req.B
	trace := ""
	if req.Q != nil {
		trace = req.Q.Trace
	}
	return &RSP_WidePacket{
		Trace:       trace,
		PayloadSize: uint64(len(packet.Body.Payload)),
		SignedWide:  packet.Header.SignedWide,
		Checksum:    packet.Body.Checksum,
	}, nil
}

func (impl *Router) AuditPacketResponse(ctx *CTX_AuditPacketResponse, req *REQ_AuditPacketResponse) (rsp *RSP_AuditPacketResponse, err error) {
	return &RSP_AuditPacketResponse{
		Header: binaryschema.AuditPacketHeader{
			Kind:      binaryschema.AuditPacketKindAudit,
			Flags:     binaryschema.AuditPacketFlagsHasItems,
			ItemCount: 2,
		},
		Body: binaryschema.AuditPacketBody{
			Items: []binaryschema.AuditPacketItem{
				{ID: 11, Code: 101},
				{ID: 22, Code: 202},
			},
			Checksum: 2,
		},
	}, nil
}
