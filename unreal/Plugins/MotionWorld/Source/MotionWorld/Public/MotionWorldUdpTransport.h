#pragma once

#include "CoreMinimal.h"

class FInternetAddr;
class FSocket;
class ISocketSubsystem;

namespace MotionWorld
{
constexpr int32 MaxUdpPayloadBytes = 65507;
constexpr int32 MaxObservationDatagramBytes = 16384;
constexpr int32 MaxActionDatagramBytes = 8192;
constexpr int32 DefaultMaxDatagramsPerPoll = 16;

struct FMotionWorldUdpTransportConfig
{
	uint16 LocalPort = 52580;
	uint16 RemotePort = 52581;
	int32 MaxInboundDatagramBytes = MaxActionDatagramBytes;
	int32 MaxOutboundDatagramBytes = MaxObservationDatagramBytes;
	int32 MaxDatagramsPerPoll = DefaultMaxDatagramsPerPoll;

	bool IsValid() const;
};

struct FMotionWorldUdpPollResult
{
	TArray<TArray<uint8>> Payloads;
	int32 DatagramsRead = 0;
	int32 RejectedUnknownSender = 0;
	int32 RejectedOversizedOrEmpty = 0;
	bool bPollBudgetExhausted = false;
};

/**
 * Owns one IPv4-loopback UDP socket. Every operation is nonblocking and every
 * poll has fixed byte/datagram bounds. This class transports bytes only; it
 * never parses JSON or mutates gameplay state.
 */
class MOTIONWORLD_API FMotionWorldUdpTransport
{
public:
	FMotionWorldUdpTransport() = default;
	~FMotionWorldUdpTransport();

	FMotionWorldUdpTransport(const FMotionWorldUdpTransport&) = delete;
	FMotionWorldUdpTransport& operator=(const FMotionWorldUdpTransport&) = delete;

	bool Open(const FMotionWorldUdpTransportConfig& InConfig);
	void Close();
	bool IsOpen() const { return Socket != nullptr; }
	bool Send(TConstArrayView<uint8> Payload);
	FMotionWorldUdpPollResult Poll();

private:
	FMotionWorldUdpTransportConfig Config;
	ISocketSubsystem* SocketSubsystem = nullptr;
	FSocket* Socket = nullptr;
	TSharedPtr<FInternetAddr> RemoteAddress;
	TArray<uint8> ReceiveBuffer;
};
} // namespace MotionWorld
